from datetime import datetime
import json
import os

from data_fetcher import load_caribbean
from plots import crop_box, plot_precip_accum, plot_precip_rate, plot_temperature, plot_wind

FORECAST_HOURS = [0, 3, 6, 12, 24, 48, 72]


def _fxx_label(fxx: int) -> str:
    return f"f{fxx:02d}"


def write_timestamp(name: str, fxx: int) -> None:
    with open(f"static/{name}_{_fxx_label(fxx)}_timestamp.txt", "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))


def image_path(name: str, fxx: int) -> str:
    return f"static/{name}_{_fxx_label(fxx)}.png"


os.makedirs("static", exist_ok=True)
available_hours = []

for fxx in FORECAST_HOURS:
    try:
        ds = load_caribbean(fxx=fxx)
        region = crop_box(ds, 12, 22, -68, -58)

        plot_temperature(region, image_path("region", fxx))
        write_timestamp("region", fxx)

        plot_wind(region, image_path("wind", fxx))
        write_timestamp("wind", fxx)

        plot_precip_accum(region, image_path("precip_accum", fxx))
        write_timestamp("precip_accum", fxx)

        plot_precip_rate(region, image_path("precip_rate", fxx), forecast_hour=fxx)
        write_timestamp("precip_rate", fxx)

        available_hours.append(_fxx_label(fxx))
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Failed to generate forecast hour {fxx}: {exc}")

with open("static/available_forecast_hours.json", "w", encoding="utf-8") as f:
    json.dump(available_hours, f)
