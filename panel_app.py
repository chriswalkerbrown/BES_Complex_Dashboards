import html
import os
import time
from pathlib import Path

STATIC_DIR = Path("static")
OUTPUT = Path("index.html")

FORECAST_OPTIONS = [
    ("0h", "f00"),
    ("1h", "f01"),
    ("2h", "f02"),
    ("3h", "f03"),
    ("6h", "f06"),
    ("12h", "f12"),
    ("24h", "f24"),
    ("48h", "f48"),
    ("72h", "f72"),
]

LAYER_OPTIONS = ["Temperature", "Wind", "Rainfall"]
RAINFALL_OPTIONS = ["Accumulated", "Rate"]


def ts_text(name: str, fhr: str) -> str:
    candidates = [
        STATIC_DIR / f"{name}_{fhr}_timestamp.txt",
        STATIC_DIR / f"{name}_f00_timestamp.txt",
        STATIC_DIR / f"{name}_timestamp.txt",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return "No timestamp available"


def image_url(name: str, fhr: str, rev: int) -> str:
    # Always point to canonical forecast-hour filenames.
    # Do not gate on local existence to avoid generating an empty state table.
    return f"static/{name}_{fhr}.png?v={rev}"


def compute_latest() -> str:
    if not STATIC_DIR.exists():
        return "Unknown"
    stamps = list(STATIC_DIR.glob("*_timestamp.txt"))
    if not stamps:
        return "Unknown"
    latest = max(stamps, key=lambda p: p.stat().st_mtime)
    return latest.read_text(encoding="utf-8").strip()


def build_state_table(rev: int) -> dict:
    state = {}
    for label, fhr in FORECAST_OPTIONS:
        state[label] = {
            "Temperature": {
                "src": image_url("region", fhr, rev),
                "ts": ts_text("region", fhr),
                "title": "Regional Temperature",
            },
            "Wind": {
                "src": image_url("wind", fhr, rev),
                "ts": ts_text("wind", fhr),
                "title": "10 m Wind Vectors",
            },
            "Rainfall": {
                "Accumulated": {
                    "src": image_url("precip_accum", fhr, rev),
                    "ts": ts_text("precip_accum", fhr),
                    "title": "Accumulated Rainfall",
                },
                "Rate": {
                    "src": image_url("precip_rate", fhr, rev),
                    "ts": ts_text("precip_rate", fhr),
                    "title": "Rainfall Rate",
                },
            },
        }
    return state


def main() -> None:
    latest = html.escape(compute_latest())
    rev = int(time.time())
    state = build_state_table(rev)

    import json

    state_json = json.dumps(state)
    forecast_buttons = "".join(
        f'<button class="btn" data-group="forecast" data-value="{lbl}">{lbl}</button>' for lbl, _ in FORECAST_OPTIONS
    )
    layer_buttons = "".join(
        f'<button class="btn" data-group="layer" data-value="{opt}">{opt}</button>' for opt in LAYER_OPTIONS
    )
    rain_buttons = "".join(
        f'<button class="btn" data-group="rain" data-value="{opt}">{opt}</button>' for opt in RAINFALL_OPTIONS
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Caribbean Weather Dashboard</title>
  <style>
    body {{ font-family: Inter, system-ui, Arial, sans-serif; background:#101419; color:#e8edf2; margin:0; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
    .card {{ background:#17202a; border:1px solid #2a3440; border-radius:14px; padding:16px; margin-bottom:14px; }}
    h1 {{ margin:0 0 6px 0; }}
    .muted {{ opacity:.8; }}
    .row {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
    .btn {{ background:#243243; border:1px solid #34465a; color:#e8edf2; padding:8px 12px; border-radius:10px; cursor:pointer; }}
    .btn.active {{ background:#2d6cdf; border-color:#2d6cdf; }}
    img {{ width:100%; max-width:980px; border-radius:10px; border:1px solid #2a3440; }}
    .warn {{ color:#ffd479; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Caribbean Weather Dashboard</h1>
      <div><strong>Last updated:</strong> {latest}</div>
      <div class="muted">Data source: NAM (NOAA)</div>
    </div>

    <div class="card">
      <div><strong>Forecast Hour</strong></div>
      <div class="row" id="forecastButtons">{forecast_buttons}</div>
      <div style="height:8px"></div>
      <div><strong>Layer</strong></div>
      <div class="row" id="layerButtons">{layer_buttons}</div>
      <div style="height:8px"></div>
      <div><strong>Rainfall Mode</strong></div>
      <div class="row" id="rainButtons">{rain_buttons}</div>
    </div>

    <div class="card">
      <h3 id="plotTitle">Regional Temperature</h3>
      <div id="warning" class="warn" style="display:none;">No image found for this selection.</div>
      <img id="plotImage" alt="weather plot" />
      <div style="margin-top:8px"><strong>Updated:</strong> <span id="plotTs"></span></div>
    </div>
  </div>

  <script>
    const STATE = {state_json};
    const selected = {{ forecast: '0h', layer: 'Temperature', rain: 'Accumulated' }};

    function setActive(group, value) {{
      document.querySelectorAll(`[data-group="${{group}}"]`).forEach(b => b.classList.toggle('active', b.dataset.value===value));
    }}

    function currentEntry() {{
      const f = STATE[selected.forecast] || STATE['0h'];
      if (selected.layer === 'Rainfall') {{
        return (f.Rainfall && f.Rainfall[selected.rain]) || {{src:null, ts:'No timestamp available', title:'Rainfall'}};
      }}
      return f[selected.layer] || {{src:null, ts:'No timestamp available', title:selected.layer}};
    }}

    function render() {{
      const e = currentEntry();
      document.getElementById('plotTitle').textContent = e.title || selected.layer;
      document.getElementById('plotTs').textContent = e.ts || 'No timestamp available';
      const img = document.getElementById('plotImage');
      const warn = document.getElementById('warning');
      if (e.src) {{
        img.style.display = 'block';
        img.src = e.src;
        warn.style.display = 'none';
      }} else {{
        img.style.display = 'none';
        warn.style.display = 'block';
      }}
      setActive('forecast', selected.forecast);
      setActive('layer', selected.layer);
      setActive('rain', selected.rain);
    }}

    document.querySelectorAll('[data-group="forecast"]').forEach(btn => btn.onclick = () => {{ selected.forecast = btn.dataset.value; render(); }});
    document.querySelectorAll('[data-group="layer"]').forEach(btn => btn.onclick = () => {{ selected.layer = btn.dataset.value; render(); }});
    document.querySelectorAll('[data-group="rain"]').forEach(btn => btn.onclick = () => {{ selected.rain = btn.dataset.value; render(); }});

    render();
  </script>
</body>
</html>
"""

    OUTPUT.write_text(html_doc, encoding="utf-8")


if __name__ == "__main__":
    main()
