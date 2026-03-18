import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import cartopy.crs as ccrs
from herbie.toolbox import EasyMap, pc
import xarray as xr


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


def _quiver_fields(lon, lat, u, v, step=5):
    if lon.ndim == 1 and lat.ndim == 1:
        lat2d, lon2d = xr.broadcast(lat, lon)
        return lon2d[::step, ::step], lat2d[::step, ::step], u[::step, ::step], v[::step, ::step]
    if lon.ndim == 2 and lat.ndim == 2:
        return lon[::step, ::step], lat[::step, ::step], u[::step, ::step], v[::step, ::step]
    lat2d, lon2d = xr.broadcast(lat, lon)
    return lon2d[::step, ::step], lat2d[::step, ::step], u[::step, ::step], v[::step, ::step]


# =============================================================================
# Meteorological derivations
# =============================================================================

def _rh_from_dewpoint(t_k, td_k):
    """Approximate relative humidity (%) from temperature and dewpoint (both K)."""
    t_c  = np.asarray(t_k,  dtype=float) - 273.15
    td_c = np.asarray(td_k, dtype=float) - 273.15
    # Magnus formula (Bolton 1980)
    es = 6.112 * np.exp(17.67 * t_c  / (t_c  + 243.5))
    e  = 6.112 * np.exp(17.67 * td_c / (td_c + 243.5))
    return np.clip(100.0 * e / es, 0.0, 100.0)


def _wetbulb_stull(t_c, rh):
    """Wet-bulb temperature (degC) via Stull (2011) empirical formula.

    Valid for -20 degC <= T <= 50 degC and 5 % <= RH <= 99 %.
    Stull, R. (2011), J. Appl. Meteorol. Climatol. 50, 2267-2269.
    """
    t  = np.asarray(t_c,  dtype=float)
    rh = np.asarray(rh,   dtype=float)
    return (
        t  * np.arctan(0.151977 * (rh + 8.313659) ** 0.5)
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh)
        - 4.686035
    )


def _et_from_lhtfl(lhtfl):
    """Convert surface latent heat net flux (W m-2) to evapotranspiration (mm day-1).

    ET = LHTFL / 2.501e6 * 86400  [mm day-1]
    Negative LHTFL (condensation) is clamped to zero.
    """
    et = np.asarray(lhtfl, dtype=float) / 2.501e6 * 86400.0
    return np.where(et < 0, 0.0, et)


# =============================================================================
# Existing plot functions
# =============================================================================

def plot_temperature(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    t2m = _first_var(ds, ["TMP_2maboveground", "t2m", "tmp", "t"])
    p = ax.pcolormesh(lon, lat, t2m - 273.15, transform=pc, cmap="coolwarm", vmin=20, vmax=30)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="degC")
    ax.set_title(f"2 m Temperature\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_wind(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    u = _first_var(ds, ["UGRD_10maboveground", "u10", "10u", "u"]).squeeze()
    v = _first_var(ds, ["VGRD_10maboveground", "v10", "10v", "v"]).squeeze()

    speed = np.sqrt(u**2 + v**2)
    pm = ax.pcolormesh(lon, lat, speed, transform=pc, cmap="viridis")
    fig.colorbar(pm, ax=ax, orientation="horizontal", pad=0.05, label="m/s")

    qlon, qlat, qu, qv = _quiver_fields(lon, lat, u, v, step=1)
    ny, nx = qu.shape[-2], qu.shape[-1]
    stride = max(1, min(ny, nx) // 20)
    ax.quiver(qlon[::stride, ::stride], qlat[::stride, ::stride],
              qu[::stride, ::stride], qv[::stride, ::stride],
              transform=pc, scale=250, width=0.0022, color="white")

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
    p = ax.pcolormesh(lon, lat, apcp, transform=pc, cmap="gnuplot2", vmin=0, vmax=100)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm")
    ax.set_title(f"Accumulated Precipitation (APCP)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_precip_rate(ds, outfile, forecast_hour=None):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES(color="white", linewidth=0.8)

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
    p = ax.pcolormesh(lon, lat, prate_hr, transform=pc, cmap="gnuplot2", vmin=0, vmax=100)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label=units)
    ax.set_title(f"{title}\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# New plot functions
# =============================================================================

def plot_wetbulb(ds, outfile):
    """Wet-bulb temperature at 2 m derived via Stull (2011)."""
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    t2m  = _first_var(ds, ["TMP_2maboveground", "t2m", "tmp", "t"]).values
    td2m = _first_var(ds, ["DPT_2maboveground", "d2m", "dpt"]).values

    rh    = _rh_from_dewpoint(t2m, td2m)
    t2m_c = t2m - 273.15
    wb    = _wetbulb_stull(t2m_c, rh)

    # Caribbean wet-bulb range ~20-32 degC; WBGT caution at 28 degC
    p = ax.pcolormesh(lon, lat, wb, transform=pc, cmap="RdYlGn_r", vmin=20, vmax=32)
    cbar = fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="degC")
    cbar.ax.axvline(28, color="red", linewidth=1.5, linestyle="--")

    ax.set_title(f"Wet-bulb Temperature (2 m, Stull 2011)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_cloud_cover(ds, outfile):
    """Total cloud cover for the entire atmospheric column (0-100 %)."""
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES(linewidth=0.8)

    lon, lat = _coords(ds)
    tcdc = _first_var(ds, ["TCDC_entireatmosphere", "tcc", "tcdc"]).squeeze()
    tcdc = xr.where(tcdc < 0, 0, xr.where(tcdc > 100, 100, tcdc))

    p = ax.pcolormesh(lon, lat, tcdc, transform=pc, cmap="Blues", vmin=0, vmax=100)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="%")
    ax.set_title(f"Total Cloud Cover (entire column)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_pressure(ds, outfile):
    """Mean sea-level pressure with contour lines."""
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    prmsl     = _first_var(ds, ["PRMSL_meansealevel", "prmsl", "msl"]).squeeze()
    prmsl_hpa = prmsl / 100.0  # Pa -> hPa

    p = ax.pcolormesh(lon, lat, prmsl_hpa, transform=pc, cmap="RdBu_r", vmin=1000, vmax=1025)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="hPa")

    try:
        lon_v = lon.values if hasattr(lon, "values") else np.asarray(lon)
        lat_v = lat.values if hasattr(lat, "values") else np.asarray(lat)
        p_v   = prmsl_hpa.values if hasattr(prmsl_hpa, "values") else np.asarray(prmsl_hpa)
        if lon_v.ndim == 2 and lat_v.ndim == 2:
            ax.contour(lon_v, lat_v, p_v, transform=pc,
                       levels=np.arange(990, 1030, 2),
                       colors="black", linewidths=0.6, alpha=0.6)
    except Exception:
        pass

    ax.set_title(f"Mean Sea-Level Pressure\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_evapotranspiration(ds, outfile):
    """Evapotranspiration (mm day-1) derived from surface latent heat flux."""
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    lhtfl = _first_var(ds, ["LHTFL_surface", "lhtfl", "slhf"]).squeeze()
    et    = _et_from_lhtfl(lhtfl.values)

    p = ax.pcolormesh(lon, lat, et, transform=pc, cmap="YlGn", vmin=0, vmax=12)
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm day-1")
    ax.set_title(f"Evapotranspiration (from LHTFL)\nET = LHTFL / Lv   Valid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_heat_fluxes(ds, outfile):
    """Side-by-side latent and sensible heat net fluxes (W m-2).

    Positive = upward from surface to atmosphere.
    """
    fig = plt.figure(figsize=(16, 8))
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.08)

    # Latent heat
    ax_l = fig.add_subplot(gs[0], projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax_l).COASTLINES()
    lon, lat = _coords(ds)
    lhtfl = _first_var(ds, ["LHTFL_surface", "lhtfl", "slhf"]).squeeze()
    pm_l = ax_l.pcolormesh(lon, lat, lhtfl, transform=pc, cmap="YlOrRd", vmin=-50, vmax=400)
    fig.colorbar(pm_l, ax=ax_l, orientation="horizontal", pad=0.05, label="W m-2")
    ax_l.set_title(f"Latent Heat Flux (LHTFL)\nValid: {ds.valid_time.item()}")

    # Sensible heat
    ax_s = fig.add_subplot(gs[1], projection=ccrs.PlateCarree())
    EasyMap("50m", crs=ds.herbie.crs, ax=ax_s).COASTLINES()
    shtfl = _first_var(ds, ["SHTFL_surface", "shtfl", "sshf"]).squeeze()
    pm_s = ax_s.pcolormesh(lon, lat, shtfl, transform=pc, cmap="RdPu", vmin=-50, vmax=200)
    fig.colorbar(pm_s, ax=ax_s, orientation="horizontal", pad=0.05, label="W m-2")
    ax_s.set_title(f"Sensible Heat Flux (SHTFL)\nValid: {ds.valid_time.item()}")

    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
