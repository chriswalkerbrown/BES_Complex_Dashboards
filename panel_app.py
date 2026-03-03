import datetime
import os

import panel as pn

pn.extension(design="native")
pn.config.theme = "dark"


STATIC_DIR = "static"
FORECAST_HOURS = ["f00", "f03"]


def _asset_path(name: str, fhr: str) -> str:
    preferred = os.path.join(STATIC_DIR, f"{name}_{fhr}.png")
    if os.path.exists(preferred):
        return preferred

    fallback = os.path.join(STATIC_DIR, f"{name}_f00.png")
    if os.path.exists(fallback):
        return fallback

    return os.path.join(STATIC_DIR, f"{name}.png")


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
    options=FORECAST_HOURS,
    button_type="primary",
    value="f00",
)

variable = pn.widgets.RadioButtonGroup(
    name="Layer",
    options=["Temperature", "Wind", "Precipitation"],
    button_type="success",
    value="Temperature",
)

precip_type = pn.widgets.RadioButtonGroup(
    name="Precipitation",
    options=["Accumulated", "Rate"],
    button_type="warning",
    value="Accumulated",
)


def _temp_layout(fhr: str) -> pn.Column:
    return pn.Column(
        pn.Card(
            pn.pane.PNG(_asset_path("saba", fhr), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('saba', fhr)}"),
            title="Saba",
            collapsed=False,
        ),
        pn.Card(
            pn.pane.PNG(_asset_path("statia", fhr), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('statia', fhr)}"),
            title="St. Eustatius",
            collapsed=False,
        ),
        pn.Card(
            pn.pane.PNG(_asset_path("region", fhr), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('region', fhr)}"),
            title="Regional Temperature",
            collapsed=False,
        ),
    )


def _wind_layout(fhr: str) -> pn.Column:
    return pn.Column(
        pn.Card(
            pn.pane.PNG(_asset_path("wind", fhr), sizing_mode="stretch_width", max_width=900),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('wind', fhr)}"),
            title="10 m Wind Vectors",
            collapsed=False,
        )
    )


def _precip_layout(precip_choice: str, fhr: str) -> pn.Column:
    if precip_choice == "Accumulated":
        image = "precip_accum"
        title = "Accumulated Precipitation"
    else:
        image = "precip_rate"
        title = "Instantaneous Precipitation"

    return pn.Column(
        pn.Card(
            pn.pane.PNG(_asset_path(image, fhr), sizing_mode="stretch_width", max_width=900),
            pn.pane.Markdown(f"**Updated:** {read_timestamp(image, fhr)}"),
            title=title,
            collapsed=False,
        )
    )


def active_view(layer: str, precip_choice: str, fhr: str):
    info = pn.pane.Alert(
        f"Displaying forecast hour **{fhr}**.",
        alert_type="light",
        margin=(0, 0, 10, 0),
    )

    if layer == "Temperature":
        return pn.Column(info, _temp_layout(fhr))
    if layer == "Wind":
        return pn.Column(info, _wind_layout(fhr))
    return pn.Column(info, _precip_layout(precip_choice, fhr))


main_view = pn.bind(
    active_view,
    layer=variable,
    precip_choice=precip_type,
    fhr=forecast_hour,
)


header = pn.pane.Markdown(
    f"# Caribbean Weather Dashboard\n"
    f"**Last updated:** {last_updated()}  \n"
    "<span style='opacity:0.8'>Data source: NAM (NOAA)</span>",
    sizing_mode="stretch_width",
)

controls = pn.Card(
    pn.Row(forecast_hour, variable, precip_type, sizing_mode="stretch_width"),
    title="Controls",
    collapsed=False,
)

app = pn.Column(
    header,
    controls,
    main_view,
    sizing_mode="stretch_width",
)

app.save("index.html", embed=True)
