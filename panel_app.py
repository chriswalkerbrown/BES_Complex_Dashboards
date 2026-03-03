import datetime
import glob
import os

import panel as pn

pn.extension(design="native")
pn.config.theme = "dark"

STATIC_DIR = "static"
FORECAST_OPTIONS = {
    "0h": "f00",
    "3h": "f03",
    "12h": "f12",
    "24h": "f24",
    "48h": "f48",
    "72h": "f72",
    "7d": "f168",
}


def _selected_fhr(label: str) -> str:
    return FORECAST_OPTIONS.get(label, "f00")


def _asset_path(name: str, fhr: str) -> str | None:
    candidates = [
        os.path.join(STATIC_DIR, f"{name}_{fhr}.png"),
        os.path.join(STATIC_DIR, f"{name}_f00.png"),
        os.path.join(STATIC_DIR, f"{name}.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    # Last-resort fallback: use any generated hour for this variable.
    matches = sorted(glob.glob(os.path.join(STATIC_DIR, f"{name}_f*.png")))
    if matches:
        return matches[0]

    return None


def read_timestamp(name: str, fhr: str) -> str:
    candidates = [
        os.path.join(STATIC_DIR, f"{name}_{fhr}_timestamp.txt"),
        os.path.join(STATIC_DIR, f"{name}_f00_timestamp.txt"),
        os.path.join(STATIC_DIR, f"{name}_timestamp.txt"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read().strip()

    matches = sorted(glob.glob(os.path.join(STATIC_DIR, f"{name}_f*_timestamp.txt")))
    if matches:
        with open(matches[0], encoding="utf-8") as f:
            return f.read().strip()

    return "No timestamp available"


def last_updated() -> str:
    times = []
    if not os.path.exists(STATIC_DIR):
        return "Unknown"

    for filename in os.listdir(STATIC_DIR):
        if filename.endswith("_timestamp.txt"):
            times.append(os.path.getmtime(os.path.join(STATIC_DIR, filename)))

    if times:
        return datetime.datetime.utcfromtimestamp(max(times)).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown"


forecast_hour = pn.widgets.RadioButtonGroup(
    name="Forecast Hour",
    options=list(FORECAST_OPTIONS.keys()),
    button_type="primary",
    value="0h",
)

variable = pn.widgets.RadioButtonGroup(
    name="Layer",
    options=["Temperature", "Wind", "Rainfall"],
    button_type="success",
    value="Temperature",
)

rainfall_type = pn.widgets.RadioButtonGroup(
    name="Rainfall",
    options=["Accumulated", "Rate"],
    button_type="warning",
    value="Accumulated",
)


def _single_card(image_name: str, title: str, fhr: str) -> pn.Column:
    asset = _asset_path(image_name, fhr)
    if asset is None:
        return pn.Column(
            pn.pane.Alert(
                f"No image found for **{title}** at **{fhr}**. "
                "Run `update_maps.py` to generate images.",
                alert_type="warning",
            )
        )

    return pn.Column(
        pn.Card(
            pn.pane.PNG(asset, sizing_mode="stretch_width", max_width=950),
            pn.pane.Markdown(f"**Updated:** {read_timestamp(image_name, fhr)}"),
            title=title,
            collapsed=False,
        )
    )


def active_view(layer: str, rainfall_choice: str, fhr_label: str):
    fhr = _selected_fhr(fhr_label)
    info = pn.pane.Alert(
        f"Displaying forecast hour **{fhr}**.",
        alert_type="light",
        margin=(0, 0, 10, 0),
    )

    if layer == "Temperature":
        return pn.Column(info, _single_card("region", "Regional Temperature", fhr))
    if layer == "Wind":
        return pn.Column(info, _single_card("wind", "10 m Wind Vectors", fhr))

    image = "precip_accum" if rainfall_choice == "Accumulated" else "precip_rate"
    title = "Accumulated Rainfall" if rainfall_choice == "Accumulated" else "Rainfall Rate"
    return pn.Column(info, _single_card(image, title, fhr))


main_view = pn.bind(
    active_view,
    layer=variable,
    rainfall_choice=rainfall_type,
    fhr_label=forecast_hour,
)

header = pn.pane.Markdown(
    f"# Caribbean Weather Dashboard\n"
    f"**Last updated:** {last_updated()}  \n"
    "<span style='opacity:0.8'>Data source: NAM (NOAA)</span>",
    sizing_mode="stretch_width",
)

controls = pn.Card(
    pn.Row(forecast_hour, variable, rainfall_type, sizing_mode="stretch_width"),
    title="Controls",
    collapsed=False,
)

app = pn.Column(header, controls, main_view, sizing_mode="stretch_width")
app.save("index.html", embed=True)
