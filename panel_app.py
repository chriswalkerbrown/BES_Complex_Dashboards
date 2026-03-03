import panel as pn
import json
import os

pn.extension(design="native")
pn.config.theme = "dark"

def read_timestamp(name):
    path = f"static/{name}_timestamp.txt"
    if os.path.exists(path):
        return open(path).read().strip()
    return "No timestamp available"

def last_updated():
    times = []
    for name in ["saba", "statia", "region", "wind", "precip_accum", "precip_rate"]:
        path = f"static/{name}_timestamp.txt"
        if os.path.exists(path):
            times.append(os.path.getmtime(path))
    if times:
        import datetime
        return datetime.datetime.utcfromtimestamp(max(times)).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown"

forecast_hour = pn.widgets.Select(
    name="Forecast Hour",
    options=[f"f{h:02d}" for h in range(0, 61, 3)],
    value="f00"
)

variable = pn.widgets.Select(
    name="Variable",
    options=["Temperature", "Wind", "Precipitation"],
    value="Temperature"
)

precip_type = pn.widgets.Select(
    name="Precipitation Type",
    options=["Accumulated (APCP)", "Instantaneous Rate (PRATE)"],
    value="Accumulated (APCP)"
)

def precip_image():
    if precip_type.value.startswith("Accum"):
        return pn.pane.PNG("static/precip_accum.png", width=600)
    return pn.pane.PNG("static/precip_rate.png", width=600)

def precip_timestamp():
    if precip_type.value.startswith("Accum"):
        return read_timestamp("precip_accum")
    return read_timestamp("precip_rate")

panel_saba = pn.Column(
    "### Saba",
    pn.pane.PNG("static/saba.png", width=600),
    pn.pane.Markdown(read_timestamp("saba")),
    css_classes=["panel-active"],
    name="panel-saba"
)

panel_statia = pn.Column(
    "### St. Eustatius",
    pn.pane.PNG("static/statia.png", width=600),
    pn.pane.Markdown(read_timestamp("statia")),
    css_classes=["panel-active"],
    name="panel-statia"
)

panel_region = pn.Column(
    "### 10° Region",
    pn.pane.PNG("static/region.png", width=600),
    pn.pane.Markdown(read_timestamp("region")),
    css_classes=["panel-active"],
    name="panel-region"
)

panel_wind = pn.Column(
    "### Wind Vectors",
    pn.pane.PNG("static/wind.png", width=600),
    pn.pane.Markdown(read_timestamp("wind")),
    css_classes=["panel-dimmed"],
    name="panel-wind"
)

panel_precip = pn.Column(
    "### Precipitation",
    pn.bind(precip_image),
    pn.bind(precip_timestamp),
    css_classes=["panel-dimmed"],
    name="panel-precip"
)

def update_classes(event):
    for p in [panel_saba, panel_statia, panel_region, panel_wind, panel_precip]:
        p.css_classes = ["panel-dimmed"]

    if variable.value == "Temperature":
        panel_saba.css_classes = ["panel-active"]
        panel_statia.css_classes = ["panel-active"]
        panel_region.css_classes = ["panel-active"]
    elif variable.value == "Wind":
        panel_wind.css_classes = ["panel-active"]
    else:
        panel_precip.css_classes = ["panel-active"]

variable.param.watch(update_classes, "value")

dashboard = pn.Column(
    "# Caribbean Weather Dashboard",
    f"**Last updated:** {last_updated()}",
    pn.Row(forecast_hour, variable),
    pn.Row(precip_type),
    panel_saba,
    panel_statia,
    panel_region,
    panel_wind,
    panel_precip,
    "Data source: NAM (NOAA)",
)

dashboard.save("index.html", embed=True)
