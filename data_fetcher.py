# data_fetcher.py (diagnostic)
from datetime import datetime
from herbie import Herbie
import xarray as xr
import logging

logging.basicConfig(level=logging.INFO)

# Keep compatibility across xarray releases by only setting the combine
# behavior option when it exists.
if "use_new_combine_kwarg_defaults" in xr.core.options.OPTIONS:
    xr.set_options(use_new_combine_kwarg_defaults=True)

REQUIRED_VARS = {
    "TMP_2maboveground",
    "UGRD_10maboveground",
    "VGRD_10maboveground",
    "APCP_surface",
    "PRATE_surface",
}

def load_caribbean(fxx=0):
    now = datetime.utcnow()
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

    H = Herbie(cycle, model="nam", product="afwaca", fxx=fxx)
    ds_list = H.xarray()

    # If single dataset returned
    if isinstance(ds_list, xr.Dataset):
        logging.info("Herbie returned a single Dataset")
        return ds_list

    logging.info("Herbie returned %d datasets (hypercubes)", len(ds_list))

    # Log variables in each hypercube
    for i, ds in enumerate(ds_list):
        logging.info("hypercube %02d: data_vars=%s coords=%s", i, list(ds.data_vars), list(ds.coords))

    # Filter hypercubes that contain at least one required variable
    filtered = []
    for ds in ds_list:
        if set(ds.data_vars) & REQUIRED_VARS:
            filtered.append(ds)

    logging.info("Selected %d hypercubes containing required vars", len(filtered))

    if not filtered:
        logging.warning("No hypercubes contained required variables; falling back to merging all hypercubes")
        merged = xr.merge(ds_list, compat="override", join="outer")
    else:
        merged = xr.merge(filtered, compat="override", join="outer")

    logging.info("Merged dataset has data_vars=%s coords=%s", list(merged.data_vars), list(merged.coords))
    return merged
