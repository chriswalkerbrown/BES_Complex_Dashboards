import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
from herbie.toolbox import EasyMap, pc
import xarray as xr


def _find_lat_lon_names(ds):
    lat_names = ["latitude", "lat", "y", "Latitude", "gridlat_0"]
    lon_names = ["longitude", "lon", "x", "Longitude", "gridlon_0"]

    lat = next((n for n in lat_names if n in ds.coords or n in ds.data_vars), None)
    lon = next((n for n in lon_names if n in ds.coords or n in ds.data_vars), None)

    if lat is None or lon is None:
        for name in ds.coords:
            arr = ds.coords[name]
            if getattr(arr, "ndim", 0) == 2:
                if lat is None and arr.min() >= -90 and arr.max() <= 90:
                    lat = name
                if lon is None and arr.min() >= -180 and arr.max() <= 360:
                    lon = name

    return lat, lon


def _first_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return ds[name]
    raise KeyError(
        f"None of the expected variables {candidates} were found. "
        f"Available vars: {list(ds.data_vars)}"
    )


def _normalize_lon_for_grid(lon_value, lon_vals):
    lon_min = float(lon_vals.min())
    lon_max = float(lon_vals.max())

    # If data uses 0..360 convention, map negative request longitudes into that range.
    if lon_min >= 0 and lon_max > 180 and lon_value < 0:
        return lon_value % 360

    # If data uses -180..180 and request is 0..360, map back.
    if lon_max <= 180 and lon_value > 180:
        return ((lon_value + 180) % 360) - 180

    return lon_value


def _subset_1d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max):
    lat_vals = ds.coords[lat_name].values
    lon_vals = ds.coords[lon_name].values

    lon_min = _normalize_lon_for_grid(lon_min, lon_vals)
    lon_max = _normalize_lon_for_grid(lon_max, lon_vals)

    lat_slice = slice(lat_min, lat_max) if lat_vals[0] < lat_vals[-1] else slice(lat_max, lat_min)
    lon_slice = slice(lon_min, lon_max) if lon_vals[0] < lon_vals[-1] else slice(lon_max, lon_min)

    out = ds.sel({lat_name: lat_slice, lon_name: lon_slice})

    # If longitude wrap-around produced an empty selection, select by nearest indices instead.
    if out.sizes.get(lon_name, 0) == 0:
        lon_center = (lon_min + lon_max) / 2
        lat_center = (lat_min + lat_max) / 2
        iy = abs(lat_vals - lat_center).argmin()
        ix = abs(lon_vals - lon_center).argmin()
        y0, y1 = max(0, iy - 5), min(len(lat_vals), iy + 6)
        x0, x1 = max(0, ix - 5), min(len(lon_vals), ix + 6)
        out = ds.isel({lat_name: slice(y0, y1), lon_name: slice(x0, x1)})

    return out


def _subset_2d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max):
    lat = ds[lat_name]
    lon = ds[lon_name]

    lon_norm = xr.where(lon > 180, lon - 360, lon)
    lon_min_norm = ((lon_min + 180) % 360) - 180
    lon_max_norm = ((lon_max + 180) % 360) - 180

    if lon_min_norm <= lon_max_norm:
        lon_mask = (lon_norm >= lon_min_norm) & (lon_norm <= lon_max_norm)
    else:
        lon_mask = (lon_norm >= lon_min_norm) | (lon_norm <= lon_max_norm)

    mask = (lat >= lat_min) & (lat <= lat_max) & lon_mask
    out = ds.where(mask, drop=True)

    return out


def crop_region(ds, lat_center, lon_center, dlat=0.5, dlon=0.5):
    lat_name, lon_name = _find_lat_lon_names(ds)
    if lat_name is None or lon_name is None:
        raise ValueError(f"Could not find latitude/longitude coords in dataset. coords: {list(ds.coords)}")

    lat_min = lat_center - dlat
    lat_max = lat_center + dlat
    lon_min = lon_center - dlon
    lon_max = lon_center + dlon

    if ds.coords[lat_name].values.ndim == 1 and ds.coords[lon_name].values.ndim == 1:
        return _subset_1d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max)

    return _subset_2d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max)


def crop_box(ds, lat_min, lat_max, lon_min, lon_max):
    lat_name, lon_name = _find_lat_lon_names(ds)

    if ds.coords[lat_name].values.ndim == 1 and ds.coords[lon_name].values.ndim == 1:
        return _subset_1d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max)

    return _subset_2d(ds, lat_name, lon_name, lat_min, lat_max, lon_min, lon_max)


def _coords(ds):
    lat_name, lon_name = _find_lat_lon_names(ds)
    return ds[lon_name], ds[lat_name]




def _quiver_fields(lon, lat, u, v, step=5):
    # Handle both 1D and 2D lon/lat coordinate grids safely for quiver plotting.
    if lon.ndim == 1 and lat.ndim == 1:
        lat2d, lon2d = xr.broadcast(lat, lon)
        return (
            lon2d[::step, ::step],
            lat2d[::step, ::step],
            u[::step, ::step],
            v[::step, ::step],
        )

    if lon.ndim == 2 and lat.ndim == 2:
        return (
            lon[::step, ::step],
            lat[::step, ::step],
            u[::step, ::step],
            v[::step, ::step],
        )

    # Mixed-dimension fallback (rare): broadcast into 2D first.
    lat2d, lon2d = xr.broadcast(lat, lon)
    return (
        lon2d[::step, ::step],
        lat2d[::step, ::step],
        u[::step, ::step],
        v[::step, ::step],
    )


def plot_temperature(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    t2m = _first_var(ds, ["TMP_2maboveground", "t2m", "tmp", "t"])
    t2m_c = t2m - 273.15

    # Fixed color scale: 20°C to 30°C 
    p = ax.pcolormesh( lon, lat, t2m_c, transform=pc, cmap="coolwarm", vmin=20, vmax=30 )
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="°C")

    ax.set_title(f"2m Temperature\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_wind(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    u = _first_var(ds, ["UGRD_10maboveground", "u10", "10u", "u"]).squeeze()
    v = _first_var(ds, ["VGRD_10maboveground", "v10", "10v", "v"]).squeeze()

    # Add a wind-speed background so there is always visible wind information,
    # even when quiver arrows become sparse.
    speed = np.sqrt((u ** 2) + (v ** 2))
    pm = ax.pcolormesh(lon, lat, speed, transform=pc, cmap="viridis")
    fig.colorbar(pm, ax=ax, orientation="horizontal", pad=0.05, label="m/s")

    qlon, qlat, qu, qv = _quiver_fields(lon, lat, u, v, step=1)

    ny, nx = qu.shape[-2], qu.shape[-1]
    stride = max(1, min(ny, nx) // 20)
    qlon = qlon[::stride, ::stride]
    qlat = qlat[::stride, ::stride]
    qu = qu[::stride, ::stride]
    qv = qv[::stride, ::stride]

    ax.quiver(qlon, qlat, qu, qv, transform=pc, scale=250, width=0.0022, color="white")

    ax.set_title(f"10 m Wind (speed + vectors)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
def plot_precip_accum(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES(color="white", linewidth=0.8)


    lon, lat = _coords(ds)
    apcp = _first_var(ds, ["APCP_surface", "tp", "apcp"])

    apcp = xr.where(apcp < 0, 0, apcp)
    # Fixed color scale: 0–100 mm 
    p = ax.pcolormesh( lon, lat, apcp, transform=pc, cmap="gnuplot2", vmin=0, vmax=100 )
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm")

    ax.set_title(f"Accumulated Precipitation (APCP)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_precip_rate(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES(color="white", linewidth=0.8)


    lon, lat = _coords(ds)
    prate = _first_var(ds, ["PRATE_surface", "prate", "tp"])
    if prate.name == "tp":
        # Fallback when an explicit rate variable is unavailable.
        # `tp` is commonly total precipitation in meters over the accumulation period.
        prate_hr = prate * 1
        title = "Precipitation (TP fallback)"
        units = "mm"
    else:
        prate_hr = prate * 1
        title = "Instantaneous Precipitation Rate (PRATE)"
        units = "mm/hr"

    prate_hr = xr.where(prate_hr < 0, 0, prate_hr)
    p = ax.pcolormesh(lon, lat, prate_hr, transform=pc, cmap="gnuplot2", vmin=0, vmax=100)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label=units)

    ax.set_title(f"{title}\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
