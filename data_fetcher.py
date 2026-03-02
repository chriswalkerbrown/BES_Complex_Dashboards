from datetime import datetime
from herbie import Herbie
import xarray as xr

def load_caribbean(fxx=0):
    now = datetime.utcnow()
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

    H = Herbie(cycle, model="nam", product="afwaca", fxx=fxx)

    ds = H.xarray()

    # Herbie returns a list of datasets when cfgrib finds multiple hypercubes
    if isinstance(ds, list):
        # Merge all hypercubes into one dataset
        ds = xr.merge(ds)

    return ds
