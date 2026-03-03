from data_fetcher import load_caribbean
from plots import (
    crop_region, crop_box,
    plot_temperature, plot_wind,
    plot_precip_accum, plot_precip_rate
)
from datetime import datetime
import os
def write_timestamp(name):
    with open(f"static/{name}_timestamp.txt", "w") as f:
        f.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
os.makedirs("static", exist_ok=True)

ds = load_caribbean()

saba = crop_region(ds, 17.63, -63.23)
plot_temperature(saba, "static/saba.png")
write_timestamp("saba")

statia = crop_region(ds, 17.48, -62.98)
plot_temperature(statia, "static/statia.png")
write_timestamp("statia")

region = crop_box(ds, 12, 22, -68, -58)
plot_temperature(region, "static/region.png")
write_timestamp("region")

plot_wind(region, "static/wind.png")
write_timestamp("wind")

plot_precip_accum(region, "static/precip_accum.png")
write_timestamp("precip_accum")

plot_precip_rate(region, "static/precip_rate.png")
write_timestamp("precip_rate")
