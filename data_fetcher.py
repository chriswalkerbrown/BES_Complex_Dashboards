from datetime import datetime
from herbie import Herbie
import xarray as xr

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

    # If Herbie returned a single dataset, just return it
    if isinstance(ds_list, xr.Dataset):
        return ds_list

    # Filter hypercubes that contain at least one required variable
    filtered = []
    for ds in ds_list:
        vars_in_ds = set(ds.data_vars)
        if vars_in_ds & REQUIRED_VARS:
            filtered.append(ds)

    # Merge only the relevant hypercubes
    merged = xr.merge(filtered, compat="override")

    return merged
