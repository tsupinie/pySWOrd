
from pysword import SPCSWO

import matplotlib as mpl
mpl.use('agg')
import pylab
from mpl_toolkits.basemap import Basemap

from descartes import PolygonPatch
from shapely.ops import transform

from datetime import datetime, timedelta

def create_image(date, bmap, lead_time=1):
    print "Testing the day-%d outlook for %s ..." % (lead_time, date.strftime("%d %B %Y"))
    cat_colors = {'TSTM':'#76ff7b', 'MRGL':'#008b00', 'SLGT':'#ffc800', 'ENH':'#f97306', 'MDT':'#ff0000', 'HIGH':'#ff00ff'}
    tor_colors = {0.02:'#008b00', 0.05:'#8b4726', 0.1:'#ffc800', 0.15:'#ff0000', 0.3:'#ff00ff', 0.45:'#912cee', 0.6:'#104e8b'}
    wind_colors = {0.05:'#8b4726', 0.15:'#ffc800', 0.3:'#ff0000', 0.45:'#ff00ff', 0.6:'#912cee'}
    hail_colors = {0.05:'#8b4726', 0.15:'#ffc800', 0.3:'#ff0000', 0.45:'#ff00ff', 0.6:'#912cee'}

    pylab.figure(dpi=200)
    swo = SPCSWO.download(date, lead_time=lead_time)
#   print "Outlook valid %s, ending %s." % (swo.valid_start.strftime("%H%MZ %d %b %Y"), swo.valid_end.strftime("%H%MZ %d %b %Y"))

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

    pylab.title("%s Day-%d SPC Convective Outlook from %s" % (date.strftime("%H%MZ"), lead_time, date.strftime("%d %B %Y")))
    pylab.savefig("otlk_%s.png" % date.strftime("%Y%m%d_%H%MZ"), dpi=pylab.gcf().dpi)
    pylab.close()

def main():
    bmap = Basemap(projection='lcc', resolution='i', 
        llcrnrlon=-120, llcrnrlat=23, urcrnrlon=-64, urcrnrlat=49,
        lat_1=33, lat_2=45, lon_0=-98, area_thresh=(1.5 * 36 * 36))

    dates = [
        datetime(2015, 4, 19, 1, 0),
        datetime(2016, 5, 21, 16, 30),
        datetime(2016, 6, 9, 1, 0),
        datetime(2016, 6, 26, 12, 0),
    ]
    for date in dates:
        create_image(date, bmap)


if __name__ == "__main__":
    main()
