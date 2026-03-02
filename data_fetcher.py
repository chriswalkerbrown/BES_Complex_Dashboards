from datetime import datetime
from herbie import Herbie

def load_caribbean(fxx=0):
    now = datetime.utcnow()
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)
    H = Herbie(cycle, model="nam", product="afwaca", fxx=fxx)
    return H.xarray()
