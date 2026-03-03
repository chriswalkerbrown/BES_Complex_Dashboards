import datetime
import os

import panel as pn

pn.extension(design="native")
pn.config.theme = "dark"


STATIC_DIR = "static"


def read_timestamp(name: str) -> str:
    path = os.path.join(STATIC_DIR, f"{name}_timestamp.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return "No timestamp available"


def last_updated() -> str:
    times = []
    for name in ["saba", "statia", "region", "wind", "precip_accum", "precip_rate"]:
        path = os.path.join(STATIC_DIR, f"{name}_timestamp.txt")
        if os.path.exists(path):
            times.append(os.path.getmtime(path))
    if times:
        return datetime.datetime.utcfromtimestamp(max(times)).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown"


# -----------------------------------------------------------------------------
# Controls
# -----------------------------------------------------------------------------

forecast_hour = pn.widgets.RadioButtonGroup(
    name="Forecast Hour",
    options=["f00"],
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


# -----------------------------------------------------------------------------
# View helpers
# -----------------------------------------------------------------------------

def _temp_layout() -> pn.Column:
    return pn.Column(
        pn.Card(
            pn.pane.PNG(os.path.join(STATIC_DIR, "saba.png"), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('saba')}") ,
            title="Saba",
            collapsed=False,
        ),
        pn.Card(
            pn.pane.PNG(os.path.join(STATIC_DIR, "statia.png"), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('statia')}") ,
            title="St. Eustatius",
            collapsed=False,
        ),
        pn.Card(
            pn.pane.PNG(os.path.join(STATIC_DIR, "region.png"), sizing_mode="stretch_width", max_width=700),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('region')}") ,
            title="Regional Temperature",
            collapsed=False,
        ),
    )


def _wind_layout() -> pn.Column:
    return pn.Column(
        pn.Card(
            pn.pane.PNG(os.path.join(STATIC_DIR, "wind.png"), sizing_mode="stretch_width", max_width=900),
            pn.pane.Markdown(f"**Updated:** {read_timestamp('wind')}") ,
            title="10 m Wind Vectors",
            collapsed=False,
        )
    )


def _precip_layout(precip_choice: str) -> pn.Column:
    if precip_choice == "Accumulated":
        image = "precip_accum.png"
        stamp = "precip_accum"
        title = "Accumulated Precipitation"
    else:
        image = "precip_rate.png"
        stamp = "precip_rate"
        title = "Instantaneous Precipitation"

    return pn.Column(
        pn.Card(
            pn.pane.PNG(os.path.join(STATIC_DIR, image), sizing_mode="stretch_width", max_width=900),
            pn.pane.Markdown(f"**Updated:** {read_timestamp(stamp)}") ,
            title=title,
            collapsed=False,
        )
    )


def active_view(layer: str, precip_choice: str, fhr: str):
    # fhr is currently informational; only latest files are generated in update_maps.py.
    info = pn.pane.Alert(
        f"Displaying **latest available data** for forecast hour **{fhr}**.",
        alert_type="light",
        margin=(0, 0, 10, 0),
    )

    if layer == "Temperature":
        return pn.Column(info, _temp_layout())
    if layer == "Wind":
        return pn.Column(info, _wind_layout())
    return pn.Column(info, _precip_layout(precip_choice))


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
