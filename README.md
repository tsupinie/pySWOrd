# pySWOrd
A parser for SPC convective outlooks

## Required Libraries
* `numpy`
* `shapely`
* `dateutil`

For plotting, `matplotlib` is suggested, and `descartes` makes plotting `shapely` polygons with `matplotlib` super easy.

## Usage
```python
from pysword import SPCSWO

# Load from text (the WWUS0n PTSDYn product, where n = 1,2,3).
swo = SPCSWO(outlook_text)

# Download from the Internet. WWUS0n PDSDYn products exist back to 24 March 2005.
from datetime import datetime

outlook_issue = datetime(2012, 4, 13, 6, 0, 0)             # Outlook issuance time
lead_time = 2                                              # Lead time in the outlook in days
swo = SPCSWO.download(outlook_issue, lead_time=lead_time)  # lead_time defaults to 1 day if not specified.

# Do stuff with the outlook
product = swo['categorical']               # Pull out the categorical outlook (specify 'tornado' for the 
                                           #  tornado outlook, 'hail' for the hail outlook, or 'wind' for
                                           #  the wind outlook).
contour_vals = product.get_contour_vals()  # Get the contour values for this outlook
for con_val in contour_vals:
    for polygon in product[con_val]:       # Loop over all contours (e.g. all SLGT risk areas)
        # Polygon is a shapely polygon representing a contour in the outlook.
```
