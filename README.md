# geocoding_frame

### Usage
<hr>

Import and initialize AddressFrame with declared fields.

```
import pandas as pd
from address_frame import AddressFrame
df = pd.read_csv('../data/test_adds.csv')
adf = AddressFrame(df, 'address', 'city', 'state', 'zipcode')
```

Clean and geocode the dataset.

```
adf.clean_streets().clean_cities().clean_zips() # optional
adf.geocode(geo_report=True) # set geo_report=True to print out short report after geocoding (could go to logs eventually)
```

Dataset will have geo field, and lat/lon.