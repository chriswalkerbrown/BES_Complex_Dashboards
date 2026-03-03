from datetime import datetime
import os

from data_fetcher import load_caribbean
from plots import (
    crop_region,
    crop_box,
    plot_temperature,
    plot_wind,
    plot_precip_accum,
    plot_precip_rate,
)


FORECAST_HOURS = [0, 3]


def _fxx_label(fxx: int) -> str:
    return f"f{fxx:02d}"


def write_timestamp(name: str, fxx: int) -> None:
    with open(f"static/{name}_{_fxx_label(fxx)}_timestamp.txt", "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))


def image_path(name: str, fxx: int) -> str:
    return f"static/{name}_{_fxx_label(fxx)}.png"


os.makedirs("static", exist_ok=True)

for fxx in FORECAST_HOURS:
    ds = load_caribbean(fxx=fxx)

    saba = crop_region(ds, 17.63, -63.23)
    plot_temperature(saba, image_path("saba", fxx))
    write_timestamp("saba", fxx)

    statia = crop_region(ds, 17.48, -62.98)
    plot_temperature(statia, image_path("statia", fxx))
    write_timestamp("statia", fxx)

    region = crop_box(ds, 12, 22, -68, -58)
    plot_temperature(region, image_path("region", fxx))
    write_timestamp("region", fxx)

    plot_wind(region, image_path("wind", fxx))
    write_timestamp("wind", fxx)

    plot_precip_accum(region, image_path("precip_accum", fxx))
    write_timestamp("precip_accum", fxx)

    plot_precip_rate(region, image_path("precip_rate", fxx))
    write_timestamp("precip_rate", fxx)
