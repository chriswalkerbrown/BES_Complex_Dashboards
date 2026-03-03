from datetime import datetime
import logging

from herbie import Herbie
import xarray as xr

logging.basicConfig(level=logging.INFO)

# Keep compatibility across xarray releases by only setting the combine
# behavior option when it exists.
if "use_new_combine_kwarg_defaults" in xr.core.options.OPTIONS:
    xr.set_options(use_new_combine_kwarg_defaults=True)


TARGET_FIELDS = {
    "TMP_2maboveground": ":TMP:2 m above ground:",
    "UGRD_10maboveground": ":UGRD:10 m above ground:",
    "VGRD_10maboveground": ":VGRD:10 m above ground:",
    "APCP_surface": ":APCP:surface:",
    "PRATE_surface": ":PRATE:surface:",
}


def _merge_datasets(datasets):
    if not datasets:
        raise ValueError("No datasets available to merge")
    if len(datasets) == 1:
        return datasets[0]
    return xr.merge(datasets, compat="override", join="outer")


def load_caribbean(fxx=0):
    now = datetime.utcnow()
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

    H = Herbie(cycle, model="nam", product="afwaca", fxx=fxx)

    selected = []
    for name, pattern in TARGET_FIELDS.items():
        try:
            ds = H.xarray(pattern)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Unable to load %s via pattern %s: %s", name, pattern, exc)
            continue

        if isinstance(ds, list):
            ds = _merge_datasets(ds)

        if isinstance(ds, xr.Dataset) and ds.data_vars:
            logging.info("Loaded %s with variables: %s", name, list(ds.data_vars))
            selected.append(ds)

    if selected:
        merged = _merge_datasets(selected)
        logging.info("Merged targeted dataset vars=%s", list(merged.data_vars))
        return merged

    logging.warning("Targeted field loads failed; falling back to full hypercube merge")
    ds_list = H.xarray()

    if isinstance(ds_list, xr.Dataset):
        logging.info("Herbie returned a single Dataset")
        return ds_list

    merged = _merge_datasets(ds_list)
    logging.info("Merged fallback dataset vars=%s", list(merged.data_vars))
    return merged
