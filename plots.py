import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from herbie.toolbox import EasyMap, pc
import xarray as xr

# -------------------------------------------------------------------
# Coordinate detection helpers
# -------------------------------------------------------------------

def _find_lat_lon_names(ds):
    lat_names = ["latitude", "lat", "y", "Latitude", "gridlat_0"]
    lon_names = ["longitude", "lon", "x", "Longitude", "gridlon_0"]

    lat = next((n for n in lat_names if n in ds.coords or n in ds.data_vars), None)
    lon = next((n for n in lon_names if n in ds.coords or n in ds.data_vars), None)

    # Try to infer from 2D coords
    if lat is None or lon is None:
        for name in ds.coords:
            arr = ds.coords[name]
            if getattr(arr, "ndim", 0) == 2:
                if lat is None and arr.min() >= -90 and arr.max() <= 90:
                    lat = name
                if lon is None and arr.min() >= -180 and arr.max() <= 360:
                    lon = name

    return lat, lon

# -------------------------------------------------------------------
# Cropping helpers
# -------------------------------------------------------------------

def crop_region(ds, lat_center, lon_center, dlat=0.5, dlon=0.5):
    lat_name, lon_name = _find_lat_lon_names(ds)
    if lat_name is None or lon_name is None:
        raise ValueError(f"Could not find latitude/longitude coords in dataset. coords: {list(ds.coords)}")

    lat_min = lat_center - dlat
    lat_max = lat_center + dlat
    lon_min = lon_center - dlon
    lon_max = lon_center + dlon

    lat_vals = ds.coords[lat_name].values
    if lat_vals.ndim == 1:
        lat_slice = slice(lat_min, lat_max) if lat_vals[0] < lat_vals[-1] else slice(lat_max, lat_min)
    else:
        lat_slice = slice(lat_min, lat_max)

    lon_vals = ds.coords[lon_name].values
    if lon_vals.ndim == 1:
        lon_slice = slice(lon_min, lon_max) if lon_vals[0] < lon_vals[-1] else slice(lon_max, lon_min)
    else:
        lon_slice = slice(lon_min, lon_max)

    return ds.sel({lat_name: lat_slice, lon_name: lon_slice})

def crop_box(ds, lat_min, lat_max, lon_min, lon_max):
    lat_name, lon_name = _find_lat_lon_names(ds)
    return ds.sel({lat_name: slice(lat_max, lat_min), lon_name: slice(lon_min, lon_max)})

# -------------------------------------------------------------------
# Plotting functions
# -------------------------------------------------------------------

def _coords(ds):
    lat_name, lon_name = _find_lat_lon_names(ds)
    return ds[lon_name], ds[lat_name]

def plot_temperature(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    t2m = ds["TMP_2maboveground"] - 273.15

    p = ax.pcolormesh(lon, lat, t2m, transform=pc, cmap="coolwarm")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="°C")

    ax.set_title(f"2m Temperature\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_wind(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    u = ds["UGRD_10maboveground"]
    v = ds["VGRD_10maboveground"]

    skip = (slice(None, None, 5), slice(None, None, 5))
    ax.quiver(lon[skip], lat[skip], u[skip], v[skip], transform=pc, scale=400, width=0.0025, color="white")

    ax.set_title(f"10 m Wind Vectors\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_precip_accum(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    apcp = ds["APCP_surface"]

    p = ax.pcolormesh(lon, lat, apcp, transform=pc, cmap="Blues")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm")

    ax.set_title(f"Accumulated Precipitation (APCP)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_precip_rate(ds, outfile):
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())

    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    lon, lat = _coords(ds)
    prate = ds["PRATE_surface"] * 3600

    p = ax.pcolormesh(lon, lat, prate, transform=pc, cmap="Purples")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm/hr")

    ax.set_title(f"Instantaneous Precipitation Rate (PRATE)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
