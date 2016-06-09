
import numpy as np

from shapely.geometry import LineString
from shapely.ops import polygonize, transform
import random

import re
from datetime import datetime, timedelta
from dateutil.tz import tzutc, tzoffset
import cPickle
import urllib2

class SPCSWOContours(object):
    def __init__(self, product, text, outline):
        self._product = product
        self._conus = outline
        self._contours = self._parse(text)

    def __getitem__(self, val):
        return self._contours[val]

    def __contains__(self, val):
        return val in self._contours

    def get_contour_vals(self):
        if self._product.lower() == "categorical":
            categories = ['TSTM', 'MRGL', 'SLGT', 'MDT', 'HIGH']
            contours = [ c for c in categories if c in self._contours.keys() ]
        else:
            contours = sorted([ c for c in self._contours.keys() if c != 'SIGN'])
        return contours

    def _parse(self, text):
        contours = {}

        if self._product.lower() == 'categorical':
            conts = re.split("[\s](?=[A-Z]{3})", text, re.S)
        else:
            conts = re.split("[\s](?=0\.|SI|TS)", text, re.S)

        for cont in conts:
            try:
                cont_val = float(cont[:6])
            except ValueError:
                cont_val = cont[:6].strip()

            if self._product.lower() == 'tornado' and cont_val == 'TSTM':
                cont_val = 0.45 

            coords = re.findall("[\d]{8}", cont)
            lats, lons = zip(*[ (float(c[:4]) / 100., float(c[4:]) / 100.) for c in coords ])
            lons = tuple([ -(lon + 100.) if lon < 50 else -lon for lon in lons ])

            if cont_val not in contours:
                contours[cont_val] = []

            contours[cont_val].extend(self._cont_to_polys(lats, lons))
        return contours

    def _cont_to_polys(self, cont_lats, cont_lons):
        polys = []

        start_idx = 0
        splits = []
        while True:
            try:
                split_idx = cont_lats[start_idx:].index(99.99)
                splits.append(start_idx + split_idx)
                start_idx += split_idx + 1
            except ValueError:
                break

        splits = [ -1 ] + splits + [ len(cont_lats) + 1 ]
        poly_lats = [ cont_lats[splits[i] + 1:splits[i + 1]] for i in xrange(len(splits) - 1) ]
        poly_lons = [ cont_lons[splits[i] + 1:splits[i + 1]] for i in xrange(len(splits) - 1) ]

        # Intersect with the US boundary shape file.
        for plat, plon in zip(poly_lats, poly_lons):
            cont = LineString(zip(plon, plat))

            if plat[0] != plat[-1] or plon[0] != plon[-1]:
                # If the line is not a closed contour, then it intersects with the edge of the US. Extend
                #   the ends a little bit to make sure it's outside the edge.
                dln = np.diff(plon)
                dlt = np.diff(plat)

                pre = [ (plon[0] - 0.5 * dln[0], plat[0] - 0.5 * dlt[0]) ]
                post = [ (plon[-1] + 0.5 * dln[-1], plat[-1] + 0.5 * dlt[-1]) ]

                cont.coords = pre + list(cont.coords) + post 

            # polygonize() will split the country into two parts: one inside the outlook and one outside.
            #   Construct test_ln that is to the right of (inside) the contour and keep only the polygon
            #   that contains the line
            test_ln = cont.parallel_offset(0.05, 'right')

            for poly in polygonize(self._conus.boundary.union(cont)):
                if (poly.crosses(test_ln) or poly.contains(test_ln)) and self._conus.contains(poly.buffer(-0.01)):
                    polys.append(poly)

        # Sort the polygons by area so we intersect the big ones with the big ones first.
        polys.sort(key=lambda p: p.area, reverse=True)

        # If any polygons intersect, replace them with their intersection.
        intsct_polys = []
        while len(polys) > 0:
            intsct_poly = polys.pop(0)
            pops = []
            for idx, poly in enumerate(polys):
                if intsct_poly.intersects(poly):
                    intsct_poly = intsct_poly.intersection(poly)
                    pops.append(idx)

            for pop_idx in pops[::-1]:
                polys.pop(pop_idx)

            intsct_polys.append(intsct_poly)
        return intsct_polys


class SPCSWO(object):
    _CST = tzoffset('CST', -6 * 3600)
    _CDT = tzoffset('CDT', -5 * 3600)

    def __init__(self, text, outline='outline.pkl'):
        self._conus = cPickle.load(open(outline))
        self._prods = self._parse(text)    

    @staticmethod
    def download(date, lead_time=1):
        url = "http://www.spc.noaa.gov/products/outlook/archive/%s/KWNSPTSDY%d_%s.txt" % (date.strftime("%Y"), lead_time, date.strftime("%Y%m%d%H%M"))
        otlk_txt = urllib2.urlopen(url).read()
        swo = SPCSWO(otlk_txt)
        return swo

    def __getitem__(self, key):
        return self._prods[key.upper()]

    def _parse(self, text):
        lines = text.split("\n")
        issued = datetime.strptime(lines[3], "%I%M %p %Z %a %b %d %Y")
        if 'CST' in lines[3]:
            self.issued = issued.replace(tzinfo=SPCSWO._CST).astimezone(tzutc())
        elif 'CDT'in lines[3]:
            self.issued = issued.replace(tzinfo=SPCSWO._CDT).astimezone(tzutc())

        match = re.search(r"([\d]{6})Z \- ([\d]{6})Z", lines[5])
        valid_start_str, valid_end_str = match.groups()
        valid_start = datetime.strptime(valid_start_str, "%d%H%M").replace(tzinfo=tzutc())
        valid_end = datetime.strptime(valid_end_str, "%d%H%M").replace(tzinfo=tzutc())
        if valid_end < valid_start:
            valid_end += ((valid_start - valid_end) + timedelta(days=1)) # Complicated because you can't pass a month to timedelta ...
        valid_len = valid_end - valid_start

        self.valid_start = valid_start.replace(year=issued.year, month=issued.month)
        self.valid_end = self.valid_start + valid_len

        products = re.findall(r"\.\.\. ([A-Z]+) \.\.\.", text)
        prods = {}
        for prod in products:
            match = re.search("\.\.\. %s \.\.\.([\w\d\s\.]+)\&\&" % prod, text, re.S)
            cont_str = match.groups()[0].strip()
            if cont_str == "":
                continue

            prods[prod] = SPCSWOContours(prod, cont_str, self._conus) 
        return prods

if __name__ == "__main__":
    import matplotlib as mpl
    mpl.use('agg')
    import pylab

    from descartes import PolygonPatch
    from mpl_toolkits.basemap import Basemap

    bmap = Basemap(projection='lcc', resolution='i', 
        llcrnrlon=-120, llcrnrlat=23, urcrnrlon=-64, urcrnrlat=49,
        lat_1=33, lat_2=45, lon_0=-98, area_thresh=(1.5 * 36 * 36))

    cat_colors = {'TSTM':'#76ff7b', 'MRGL':'#008b00', 'SLGT':'#ffc800', 'ENH':'#f97306', 'MDT':'#ff0000', 'HIGH':'#ff00ff'}
    tor_colors = {0.02:'#008b00', 0.05:'#8b4726', 0.1:'#ffc800', 0.15:'#ff0000', 0.3:'#ff00ff', 0.45:'#912cee', 0.6:'#104e8b'}
    wind_colors = {0.05:'#8b4726', 0.15:'#ffc800', 0.3:'#ff0000', 0.45:'#ff00ff', 0.6:'#912cee'}
    hail_colors = {0.05:'#8b4726', 0.15:'#ffc800', 0.3:'#ff0000', 0.45:'#ff00ff', 0.6:'#912cee'}

    date = datetime(2016, 5, 21, 16, 30, 0)
    
    pylab.figure(dpi=200)
    swo = SPCSWO.download(date)

    pylab.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.9)

    prod = swo['categorical']
    for name in prod.get_contour_vals():
        colors = cat_colors

        conts = prod[name]
        for cont in conts:
            proj_cont = transform(lambda lon, lat: bmap(lon, lat), cont)
            pylab.gca().add_patch(PolygonPatch(proj_cont, fc=colors[name], ec=colors[name]))

    bmap.drawcoastlines()
    bmap.drawcountries()
    bmap.drawstates()

    pylab.title("%s SPC Convective Outlook for %s" % (date.strftime("%H%MZ"), date.strftime("%d %B %Y")))
    pylab.savefig('otlk.png', dpi=pylab.gcf().dpi)
