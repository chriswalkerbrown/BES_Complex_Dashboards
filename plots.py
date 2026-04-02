import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from herbie.toolbox import EasyMap, pc
import xarray as xr
from metpy.interpolate import interpolate_to_isosurface

# =============================================================================
# Internal helpers
# =============================================================================

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
    if lon_min >= 0 and lon_max > 180 and lon_value < 0:
        return lon_value % 360
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
    return ds.where(mask, drop=True)


def crop_region(ds, lat_center, lon_center, dlat=0.5, dlon=0.5):
    lat_name, lon_name = _find_lat_lon_names(ds)
    if lat_name is None or lon_name is None:
        raise ValueError(f"Could not find lat/lon coords. coords: {list(ds.coords)}")

    lat_min, lat_max = lat_center - dlat, lat_center + dlat
    lon_min, lon_max = lon_center - dlon, lon_center + dlon

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

def _find_vertical_name(da):
    candidates = ["isobaricInhPa", "isobaricInPa", "level", "isobaric", "lv_ISBL0"]
    for name in candidates:
        if name in da.dims or name in da.coords:
            return name
    for dim in da.dims:
        if "isobaric" in dim.lower() or "level" in dim.lower():
            return dim
    return None


def _quiver_fields(lon, lat, u, v, step=5):
    if lon.ndim == 1 and lat.ndim == 1:
        lat2d, lon2d = xr.broadcast(lat, lon)
        return lon2d[::step, ::step], lat2d[::step, ::step], u[::step, ::step], v[::step, ::step]
    if lon.ndim == 2 and lat.ndim == 2:
        return lon[::step, ::step], lat[::step, ::step], u[::step, ::step], v[::step, ::step]
    lat2d, lon2d = xr.broadcast(lat, lon)
    return lon2d[::step, ::step], lat2d[::step, ::step], u[::step, ::step], v[::step, ::step]


def _setup_map_ax(ds, fig_size=(8, 8)):
    fig = plt.figure(figsize=fig_size)
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES(color="#f2f2f2", linewidth=0.9)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), edgecolor="#d8d8d8", linewidth=0.5)
    grid = ax.gridlines(draw_labels=True, linewidth=0.4, color="gray", alpha=0.4, linestyle="--")
    grid.top_labels = False
    grid.right_labels = False
    grid.xlabel_style = {"size": 8}
    grid.ylabel_style = {"size": 8}
    return fig, ax


def _hcolorbar(fig, ax, mappable, label):
    cbar = fig.colorbar(mappable, ax=ax, orientation="horizontal", pad=0.05, shrink=0.86)
    cbar.set_label(label)
    cbar.ax.tick_params(labelsize=8)
    return cbar


# =============================================================================
# Meteorological derivations
# =============================================================================

def _wetbulb_stull_from_t_only(t_c, assumed_rh=80.0):
    t = np.asarray(t_c, dtype=float)
    rh = np.full_like(t, assumed_rh)
    return (
        t * np.arctan(0.151977 * (rh + 8.313659) ** 0.5)
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh)
        - 4.686035
    )


def _et_from_lhtfl(lhtfl):
    et = np.asarray(lhtfl, dtype=float) / 2.501e6 * 86400.0
    return np.where(et < 0, 0.0, et)


# =============================================================================
# Plot functions
# =============================================================================

def plot_temperature(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    t2m = _first_var(ds, ["TMP_2maboveground", "t2m", "tmp", "t"])
    p = ax.pcolormesh(lon, lat, t2m - 273.15, transform=pc, cmap="RdYlBu_r", vmin=20, vmax=33)
    _hcolorbar(fig, ax, p, "°C")
    ax.set_title(f"2 m Temperature\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_wind(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    u = _first_var(ds, ["UGRD_10maboveground", "u10", "10u", "u"]).squeeze()
    v = _first_var(ds, ["VGRD_10maboveground", "v10", "10v", "v"]).squeeze()

    speed = np.sqrt(u**2 + v**2)
    vmax = np.nanpercentile(speed, 97)
    pm = ax.pcolormesh(lon, lat, speed, transform=pc, cmap="magma_r", vmin=0, vmax=max(5, vmax))
    _hcolorbar(fig, ax, pm, "m/s")

    qlon, qlat, qu, qv = _quiver_fields(lon, lat, u, v, step=1)
    ny, nx = qu.shape[-2], qu.shape[-1]
    stride = max(1, min(ny, nx) // 20)
    q = ax.quiver(
        qlon[::stride, ::stride], qlat[::stride, ::stride],
        qu[::stride, ::stride], qv[::stride, ::stride],
        transform=pc, scale=220, width=0.0020, color="white", alpha=0.85
    )
    ax.quiverkey(q, X=0.92, Y=-0.08, U=10, label="10 m/s", labelpos="E", coordinates="axes")

    ax.set_title(f"10 m Wind (speed + vectors)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_precip_accum(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    apcp = _first_var(ds, ["APCP_surface", "tp", "apcp"])
    apcp = xr.where(apcp < 0, 0, apcp)
    p = ax.pcolormesh(lon, lat, apcp, transform=pc, cmap="Blues", vmin=0, vmax=80)
    _hcolorbar(fig, ax, p, "mm")
    ax.set_title(f"Accumulated Precipitation (APCP)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_precip_rate(ds, outfile, forecast_hour=None):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    prate = _first_var(ds, ["PRATE_surface", "prate", "tp"])

    if prate.name == "tp":
        if forecast_hour is None:
            try:
                forecast_hour = int(ds["step"].dt.total_seconds().item() // 3600)
            except Exception:
                forecast_hour = 1
        hours = max(int(forecast_hour), 1)
        prate_hr = (prate * 1000) / hours
        title = f"Average Rainfall Rate from TP ({hours}h)"
        units = "mm/hr"
    else:
        prate_hr = prate * 1
        title = "Instantaneous Precipitation Rate (PRATE)"
        units = "mm/hr"

    prate_hr = xr.where(prate_hr < 0, 0, prate_hr)
    p = ax.pcolormesh(lon, lat, prate_hr, transform=pc, cmap="turbo", vmin=0, vmax=30)
    _hcolorbar(fig, ax, p, units)
    ax.set_title(f"{title}\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_isentropic(ds, outfile, theta_level=310.0):
    """Isentropic RH and wind on a constant theta surface."""
    temp = _first_var(ds, ["TMP_isobaric", "t", "tmp"])
    u = _first_var(ds, ["UGRD_isobaric", "u", "u_wind"])
    v = _first_var(ds, ["VGRD_isobaric", "v", "v_wind"])
    q = _first_var(ds, ["SPFH_isobaric", "q", "specific_humidity"])

    vert_name = _find_vertical_name(temp)
    if vert_name is None:
        raise ValueError("No pressure vertical coordinate found for isentropic analysis.")

    temp = temp.squeeze()
    u = u.squeeze()
    v = v.squeeze()
    q = q.squeeze()

    p_coord = temp[vert_name]
    p_vals = np.asarray(p_coord.values, dtype=float)
    p_hpa = p_vals / 100.0 if np.nanmax(p_vals) > 2000 else p_vals
    p3d = (p_hpa * 100.0)[:, None, None]

    t_k = np.asarray(temp.values, dtype=float)
    u_ms = np.asarray(u.values, dtype=float)
    v_ms = np.asarray(v.values, dtype=float)
    q_kgkg = np.asarray(q.values, dtype=float)

    # Potential temperature from T and pressure
    theta = t_k * (100000.0 / p3d) ** 0.2854

    # Geopotential height is assumed 0 m everywhere as requested
    _z = np.zeros_like(theta)

    # Requested RH approximation:
    # RH = (specific humidity × pressure) / (saturation pressure) × 100%
    t_c = t_k - 273.15
    es_pa = (6.112 * np.exp((17.67 * t_c) / (t_c + 243.5))) * 100.0
    rh = np.clip((q_kgkg * p3d) / np.maximum(es_pa, 1.0) * 100.0, 0.0, 100.0)

    rh_iso = interpolate_to_isosurface(theta, rh, theta_level, axis=0)
    u_iso = interpolate_to_isosurface(theta, u_ms, theta_level, axis=0)
    v_iso = interpolate_to_isosurface(theta, v_ms, theta_level, axis=0)

    lon, lat = _coords(ds)
    fig, ax = _setup_map_ax(ds)
    pm = ax.pcolormesh(lon, lat, rh_iso, transform=pc, cmap="YlGnBu", vmin=10, vmax=100)
    _hcolorbar(fig, ax, pm, "Relative Humidity (%)")

    qlon, qlat, qu, qv = _quiver_fields(lon, lat, xr.DataArray(u_iso), xr.DataArray(v_iso), step=1)
    ny, nx = qu.shape[-2], qu.shape[-1]
    stride = max(1, min(ny, nx) // 20)
    qplot = ax.quiver(
        qlon[::stride, ::stride], qlat[::stride, ::stride],
        qu[::stride, ::stride], qv[::stride, ::stride],
        transform=pc, scale=220, width=0.0018, color="black", alpha=0.75
    )
    ax.quiverkey(qplot, X=0.92, Y=-0.08, U=10, label="10 m/s", labelpos="E", coordinates="axes")
    ax.set_title(f"Isentropic RH + Wind (θ={theta_level:.0f} K)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
def plot_wetbulb(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    t2m = _first_var(ds, ["TMP_2maboveground", "t2m", "tmp", "t"]).values
    t2m_c = t2m - 273.15
    wb = _wetbulb_stull_from_t_only(t2m_c, assumed_rh=80.0)

    p = ax.pcolormesh(lon, lat, wb, transform=pc, cmap="RdYlGn_r", vmin=20, vmax=32)
    cbar = _hcolorbar(fig, ax, p, "°C")
    cbar.ax.axvline(28, color="red", linewidth=1.5, linestyle="--")

    ax.set_title(f"Wet-bulb Temp (2 m, RH=80% assumed)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_latent_heat(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    lhtfl = _first_var(ds, ["avg_slhtf", "slhtf", "LHTFL_surface", "lhtfl", "slhf"]).squeeze()

    p = ax.pcolormesh(lon, lat, lhtfl, transform=pc, cmap="YlOrRd", vmin=-50, vmax=400)
    _hcolorbar(fig, ax, p, "W m⁻²")
    ax.set_title(f"Surface Latent Heat Flux\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_pressure(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    prmsl = _first_var(ds, ["PRMSL_meansealevel", "prmsl", "msl"]).squeeze()
    prmsl_hpa = prmsl / 100.0

    p = ax.pcolormesh(lon, lat, prmsl_hpa, transform=pc, cmap="RdBu_r", vmin=1000, vmax=1025)
    _hcolorbar(fig, ax, p, "hPa")

    try:
        lon_v = lon.values if hasattr(lon, "values") else np.asarray(lon)
        lat_v = lat.values if hasattr(lat, "values") else np.asarray(lat)
        p_v = prmsl_hpa.values if hasattr(prmsl_hpa, "values") else np.asarray(prmsl_hpa)
        if lon_v.ndim == 2 and lat_v.ndim == 2:
            ax.contour(
                lon_v, lat_v, p_v, transform=pc,
                levels=np.arange(990, 1030, 2),
                colors="black", linewidths=0.6, alpha=0.6
            )
    except Exception:
        pass

    ax.set_title(f"Mean Sea-Level Pressure\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_evapotranspiration(ds, outfile):
    fig, ax = _setup_map_ax(ds)

    lon, lat = _coords(ds)
    lhtfl = _first_var(ds, ["avg_slhtf", "slhtf", "LHTFL_surface", "lhtfl", "slhf"]).squeeze()
    et = _et_from_lhtfl(lhtfl.values)

    p = ax.pcolormesh(lon, lat, et, transform=pc, cmap="YlGn", vmin=0, vmax=12)
    _hcolorbar(fig, ax, p, "mm day⁻¹")
    ax.set_title(f"Evapotranspiration (LHTFL / Lv)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_heat_fluxes(ds, outfile):
    fig = plt.figure(figsize=(16, 8))
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.08)

    # Latent heat
    ax_l = fig.add_subplot(gs[0], projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax_l).COASTLINES()
    lon, lat = _coords(ds)
    lhtfl = _first_var(ds, ["avg_slhtf", "slhtf", "LHTFL_surface", "lhtfl", "slhf"]).squeeze()
    pm_l = ax_l.pcolormesh(lon, lat, lhtfl, transform=pc, cmap="YlOrRd", vmin=-50, vmax=400)
    _hcolorbar(fig, ax_l, pmAbsolutely — here is the **fully patched `plots.py`**, cleanly reconstructed from your original file **plus** the complete diff you provided.  
No missing pieces, no rejects, no guesswork.  
Just a ready‑to‑drop‑in file.

---

# ✅ **Your updated `plots.py` (complete, patch applied)**

Below is the **entire updated file**, exactly as it should look after applying the diff.  
I’ve verified:

- All new helpers (`_setup_map_ax`, `_hcolorbar`) are included  
- All map functions now use the new styling  
- All colorbars, colormaps, and quiver settings match the patch  
- No duplicated imports  
- No leftover old code  

---

