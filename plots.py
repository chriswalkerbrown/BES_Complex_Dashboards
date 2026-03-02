import matplotlib.pyplot as plt
from herbie.toolbox import EasyMap, pc

def plot_temperature(ds, outfile):
    fig, ax = plt.subplots(figsize=(8, 8))
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    t2m = ds["TMP_2maboveground"] - 273.15
    p = ax.pcolormesh(ds.longitude, ds.latitude, t2m, transform=pc, cmap="coolwarm")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="°C")

    ax.set_title(f"2m Temperature\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_wind(ds, outfile):
    fig, ax = plt.subplots(figsize=(8, 8))
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    u = ds["UGRD_10maboveground"]
    v = ds["VGRD_10maboveground"]

    skip = (slice(None, None, 5), slice(None, None, 5))

    ax.quiver(
        ds.longitude[skip],
        ds.latitude[skip],
        u[skip],
        v[skip],
        transform=pc,
        scale=400,
        width=0.0025,
        color="white"
    )

    ax.set_title(f"10 m Wind Vectors\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_precip_accum(ds, outfile):
    fig, ax = plt.subplots(figsize=(8, 8))
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    apcp = ds["APCP_surface"]
    p = ax.pcolormesh(ds.longitude, ds.latitude, apcp, transform=pc, cmap="Blues")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm")

    ax.set_title(f"Accumulated Precipitation (APCP)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_precip_rate(ds, outfile):
    fig, ax = plt.subplots(figsize=(8, 8))
    EasyMap("50m", crs=ds.herbie.crs, ax=ax).COASTLINES()

    prate = ds["PRATE_surface"] * 3600
    p = ax.pcolormesh(ds.longitude, ds.latitude, prate, transform=pc, cmap="Purples")
    fig.colorbar(p, ax=ax, orientation="horizontal", pad=0.05, label="mm/hr")

    ax.set_title(f"Instantaneous Precipitation Rate (PRATE)\nValid: {ds.valid_time.item()}")
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

def crop_region(ds, lat_center, lon_center, dlat=0.5, dlon=0.5):
    return ds.sel(
        latitude=slice(lat_center + dlat, lat_center - dlat),
        longitude=slice(lon_center - dlon, lon_center + dlon)
    )

def crop_box(ds, lat_min, lat_max, lon_min, lon_max):
    return ds.sel(
        latitude=slice(lat_max, lat_min),
        longitude=slice(lon_min, lon_max)
    )
