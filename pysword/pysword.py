
import numpy as np

from shapely.geometry import MultiLineString, LineString, Point
from shapely.ops import polygonize, transform

import re
import os
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

    @property
    def name(self):
        return self._product.lower()

    @property
    def contour_vals(self):
        if self.name == "categorical":
            categories = ['TSTM', 'MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH']
            contours = [ c for c in categories if c in self._contours.keys() ]
        else:
            contours = sorted([ c for c in self._contours.keys() if c != 'SIGN'])
        return contours

    def _parse(self, text):
        contours = {}

        if text == "":
            return contours

        if self.name == 'categorical':
            conts = re.split("[\s](?=[A-Z]{3})", text, re.S)
        else:
            conts = re.split("[\s](?=0\.|SI|TS)", text, re.S)

        for cont in conts:
            try:
                cont_val = float(cont[:6])
            except ValueError:
                cont_val = cont[:6].strip()

            # Dirty hack for the 7 April 2006 20Z tornado outlook, which encodes the 45% contour as a TSTM contour for 
            #   some reason. Hopefully, I don't have to do too many of these.
            if self.name == 'tornado' and cont_val == 'TSTM':
                cont_val = 0.45 

            coords = re.findall("[\d]{8}", cont)
            lats, lons = zip(*[ (float(c[:4]) / 100., float(c[4:]) / 100.) for c in coords ])
            lons = tuple([ -(lon + 100.) if lon < 50 else -lon for lon in lons ])

            if cont_val not in contours:
                contours[cont_val] = {}

            contours[cont_val].update(self._cont_to_polys(lats, lons, cont_val))

        for cont_val in contours.keys():
            contours[cont_val] = self._check_intersections(contours[cont_val], cont_val)
            contours[cont_val] = [ c for v in contours[cont_val].values() for c in v ]

        return contours

    def _cont_to_polys(self, cont_lats, cont_lons, cont_val):
        """
        Take the lat/lon contours, split them into their different segments, and create polygons out of them. Contours
        that stretch from border to border will end up covering large sections of the country. That's okay; we'll take
        care of that later.
        """
        polys = {}

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

                pre = [ (plon[0] - 0.03 * dln[0], plat[0] - 0.03 * dlt[0]) ]
                post = [ (plon[-1] + 0.03 * dln[-1], plat[-1] + 0.03 * dlt[-1]) ]

                cont.coords = pre + list(cont.coords) + post 

            # polygonize() will split the country into two parts: one inside the outlook and one outside.
            #   Construct test_ln that is to the right of (inside) the contour and keep only the polygon
            #   that contains the line
            test_ln = cont.parallel_offset(0.05, 'right')

            polys[cont] = []

            for poly in polygonize(self._conus.boundary.union(cont)):
                if (poly.crosses(test_ln) or poly.contains(test_ln)) and self._conus.contains(poly.buffer(-0.01)):
                    polys[cont].append(poly)

        return polys

    def _check_intersections(self, poly_bdy_list, cont_val):
        """
        Check for any intersections between polygons. This happens when contours stretch from one border to another, say
        a large general TSTM area stretching from the Mexican to Canadian border.
        """

        def line_distance(l1, l2):
            if hasattr(l1, 'geoms'):
                pts1 = [ Point(c) for ls in l1.geoms for c in ls.coords ]
            else:
                pts1 = [ Point(c) for c in l1.coords ]

            if hasattr(l2, 'geoms'):
                pts2 = [ Point(c) for ls in l2.geoms for c in ls.coords ]
            else:
                pts2 = [ Point(c) for c in l2.coords ]

            lpts1 = [ l2.interpolate(l2.project(pt)) for pt in pts1 ]
            lpts2 = [ l1.interpolate(l1.project(pt)) for pt in pts2 ]

            dists1 = [ np.hypot(p.x - l.x, p.y - l.y) for p, l in zip(pts1, lpts1) ]
            dists2 = [ np.hypot(p.x - l.x, p.y - l.y) for p, l in zip(pts2, lpts2) ]
            return min(dists1 + dists2)

        def any_intersections(poly_list):
            for idx, p1 in enumerate(poly_list):
                for p2 in poly_list[(idx + 1):]:
                    if p1.intersects(p2):
                        return True
            return False

        def build_bdy_lookup(poly_dict):
            bdy_lookup = {}
            for con, polys in poly_dict.iteritems():
                for poly in polys:
                    bdy_lookup[poly] = con
            return bdy_lookup

        def intersect_poly_list(poly_list):
            after_polys = []
            while any_intersections(poly_list):
                poly_list.sort(key=lambda p: p.area, reverse=True)
                tgt_poly = poly_list.pop(0)
                pop_idxs = []
                for idx, intsct in enumerate(poly_list):
                    if tgt_poly.intersects(intsct):
                        tgt_poly = tgt_poly.intersection(intsct)
                        pop_idxs.append(idx)

                for idx in sorted(pop_idxs, reverse=True):
                    poly_list.pop(idx)

                after_polys.append(tgt_poly)
            after_polys.extend(poly_list)
            return after_polys

        # Build a dictionary to look up which poly goes with which contour.
        bdy_lookup = build_bdy_lookup(poly_bdy_list)
        poly_list = bdy_lookup.keys()

        # If any polygons intersect, replace them with their intersection.
        while any_intersections(poly_list):
            # Sort the polygons by area so we intersect the big ones with the big ones first.
            poly_list.sort(key=lambda p: p.area, reverse=True)

            # Our target is the largest polygon
            target_poly = poly_list.pop(0)
            target_bdy = bdy_lookup[target_poly]

            # Now use the contour that goes with the target polygon and find the closest contour
            bdy_list = poly_bdy_list.keys()
            bdy_list.sort(key=lambda b: line_distance(target_bdy, b))
            if len(bdy_list) > 1:
                bdy_list.pop(0)
                while not any( target_poly.intersects(p) for p in poly_bdy_list[bdy_list[0]] ):
                    bdy_list.pop(0)

                # Take all polygons created by these contours and intersect as many as we can with
                #   each other, starting with the biggest ones.
                intsct_bdy = bdy_list[0]
                intsct_polys = poly_bdy_list[target_bdy] + poly_bdy_list[intsct_bdy]
                after_polys = intersect_poly_list(intsct_polys)

                # Remove the old polygons and form the new boundary
                poly_bdy_list.pop(target_bdy)
                poly_bdy_list.pop(intsct_bdy)
                new_bdy = target_bdy.union(intsct_bdy)
                poly_bdy_list[new_bdy] = after_polys
            else:
                bdy = bdy_list[0]
                intsct_polys = intersect_poly_list(poly_bdy_list[bdy])
                poly_bdy_list[bdy] = intsct_polys

            # Rebuild the lookup dictionary and arrays
            bdy_lookup = build_bdy_lookup(poly_bdy_list)
            poly_list = bdy_lookup.keys()

        return poly_bdy_list


class SPCSWO(object):
    _CST = tzoffset('CST', -6 * 3600)
    _CDT = tzoffset('CDT', -5 * 3600)

    def __init__(self, text, outline=os.path.join(os.path.dirname(__file__), 'data', 'outline.pkl')):
        self._conus = cPickle.load(open(outline))
        self._prods = self._parse(text)    

    @classmethod
    def download(cls, date, lead_time=1):
        if lead_time == 1 and date.hour == 6:
            # The 06Z Outlooks on day 1 are filed under 12Z, their valid start time. That's slightly unintuitive, so 
            #   let's fix that.
            dl_date = date.replace(hour=12)
        else:
            dl_date = date

        url = "http://www.spc.noaa.gov/products/outlook/archive/%s/KWNSPTSDY%d_%s.txt" % (dl_date.strftime("%Y"), 
            lead_time, dl_date.strftime("%Y%m%d%H%M"))
        try:
            otlk_txt = urllib2.urlopen(url).read()
        except urllib2.URLError:
            raise ValueError("A day-%d outlook from %s could not be found." % 
                (lead_time, date.strftime("%H%MZ %d %b %Y")))
        swo = cls(otlk_txt)
        return swo
    
    @classmethod
    def read(cls, file_path):
        with open(file_path, "r") as IN:
            otlk_txt = IN.read()
        return cls(otlk_txt)

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
            valid_end += ((valid_start - valid_end) + timedelta(days=1))
        valid_len = valid_end - valid_start

        self.valid_start = valid_start.replace(year=issued.year, month=issued.month)
        self.valid_end = self.valid_start + valid_len

        products = re.findall(r"\.\.\. ([A-Z ]+) \.\.\.", text)
        prods = {}
        for prod in products:
            match = re.search("\.\.\. %s \.\.\.([\w\d\s\.]+)\&\&" % prod, text, re.S)
            cont_str = match.groups()[0].strip()

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

    date = datetime(2006, 4, 7, 20, 0, 0)
    lead_time = 1

    pylab.figure(dpi=200)
    swo = SPCSWO.download(date, lead_time=lead_time)
    print "Outlook valid %s, ending %s." % (swo.valid_start.strftime("%H%MZ %d %b %Y"), swo.valid_end.strftime("%H%MZ %d %b %Y"))

    pylab.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.9)

    prod = swo['wind']
    for name in prod.contour_vals:
        colors = wind_colors

        conts = prod[name]
        for cont in conts:
            proj_cont = transform(lambda lon, lat: bmap(lon, lat), cont)
            pylab.gca().add_patch(PolygonPatch(proj_cont, fc=colors[name], ec=colors[name]))

    bmap.drawcoastlines()
    bmap.drawcountries()
    bmap.drawstates()

    pylab.title("%s Day-%d SPC Convective Outlook from %s" % (date.strftime("%H%MZ"), lead_time, date.strftime("%d %B %Y")))
    pylab.savefig('otlk.png', dpi=pylab.gcf().dpi)
