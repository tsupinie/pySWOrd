# pySWOrd
A parser for SPC severe weather outlooks. Specifically, pySWOrd will pull out the contours from an SPC outlook and store them as polygons. This allows one to do things such as compute the area enclosed by a contour, find out whether specific points are inside a contour, or to plot an outlook.

## Required Libraries
* `numpy`
* `shapely`
* `dateutil`
* `setuptools`

For plotting, `matplotlib` + `basemap` is suggested, and `descartes` makes plotting `shapely` polygons with `matplotlib` super easy.

## Setup
Run `python setup.py install` from the package root.

## Usage
```python
from pysword import SPCSWO

# Parse the product text (the WWUS0n PTSDYn product, where n = 1,2,3).
swo = SPCSWO(outlook_text)

# Load the text from a local file.
swo = SPCSWO.read('/path/to/ptsdyn.txt')

# Download from the Internet. WWUS0n PTSDYn products exist back to 24 March 2005.
from datetime import datetime

outlook_issue = datetime(2012, 4, 13, 6, 0, 0)             # Outlook issuance time
lead_time = 2                                              # Lead time in the outlook in days
swo = SPCSWO.download(outlook_issue, lead_time=lead_time)  # lead_time defaults to 1 day if not specified.

# Do stuff with the outlook
product = swo['categorical']      # Pull out the categorical outlook (specify 'tornado' for the 
                                  #    tornado outlook, 'hail' for the hail outlook, 'wind' for
                                  #    the wind outlook, or 'any severe' for probability of any
                                  #    severe on days 2 and 3.).
contour_vals = product.contours   # Get the contour values for this outlook
prod_name = product.name          # Get the product name ('categorical', 'tornado', etc.)
for con_val in contour_vals:
    for polygon in product[con_val]:       # Loop over all contours (e.g. all SLGT risk areas)
        # polygon is a shapely polygon representing a contour in the outlook. The vertices are lon, lat
        # coordinates. You can use shapely.ops.transform() and basemap to transform to x, y coordinates.
```
