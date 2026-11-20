"""Rebuild data/data.js from a QGIS GeoPackage (stdlib only).
Usage: python update_data.py path/to/Ghana_Territories.gpkg
Run it again after editing attributes or styles in QGIS, then re-upload data/data.js."""
import sqlite3, struct, json, sys, xml.etree.ElementTree as ET
SRC = sys.argv[1] if len(sys.argv) > 1 else 'Ghana_Territories.gpkg'
KEYS = {'Electrified HH Per Location': 'loc', 'Electrified HH per Terr.': 'terrPts',
        'ghana_restructuring Regional': 'regions', 'ghana_restructuring_4_territory New': 'territories'}
DROP = {'altitudemode','tessellate','extrude','visibility','draworder','icon','timestamp','begin','end',
        'ogc_fid','ogc_fid0','description','layer','path','pkuid'}
def wkb(b, o):
    e = '<' if b[o] == 1 else '>'; raw = struct.unpack(e+'I', b[o+1:o+5])[0]; o += 5
    z = bool(raw & 0x80000000) or raw // 1000 in (1, 3); m = bool(raw & 0x40000000) or raw // 1000 in (2, 3)
    t = (raw & 0xFFFF) % 1000; step = 8 * (2 + z + m)   # Z/M values are skipped, only X/Y are kept
    def pt(i): return list(struct.unpack(e+'dd', b[i:i+16]))
    if t == 1: return {"type": "Point", "coordinates": pt(o)}, o + step
    if t == 3:
        n = struct.unpack(e+'I', b[o:o+4])[0]; o += 4; rings = []
        for _ in range(n):
            k = struct.unpack(e+'I', b[o:o+4])[0]; o += 4
            rings.append([pt(o + step*i) for i in range(k)]); o += step*k
        return {"type": "Polygon", "coordinates": rings}, o
    if t == 6:
        n = struct.unpack(e+'I', b[o:o+4])[0]; o += 4; ps = []
        for _ in range(n):
            g, o = wkb(b, o); ps.append(g["coordinates"])
        return {"type": "MultiPolygon", "coordinates": ps}, o
    raise ValueError('unsupported geometry %s' % raw)
def geom(b):
    n = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(b[3] >> 1) & 7]; return wkb(b, 8 + n)[0]
def rnd(v): return [round(v[0], 5), round(v[1], 5)] if isinstance(v[0], float) else [rnd(i) for i in v]
def hexcol(s):
    r, g, b = [int(x) for x in s.split(',')[:3]]; return '#%02x%02x%02x' % (r, g, b)
def symcolor(sym):
    for o in list(sym.iter('Option')) + list(sym.iter('prop')):
        if (o.get('name') or o.get('k')) == 'color': return hexcol(o.get('value') or o.get('v'))
db = sqlite3.connect(SRC); out = {'layers': {}, 'styles': {}}
for table, key in KEYS.items():
    cur = db.execute('select * from "%s"' % table); names = [d[0] for d in cur.description]; feats = []
    for row in cur:
        d = dict(zip(names, row)); g = geom(d.pop('geom')); d.pop('fid', None)
        d = {k: v for k, v in d.items() if k not in DROP}; g['coordinates'] = rnd(g['coordinates'])
        feats.append({"type": "Feature", "properties": d, "geometry": g})
    out['layers'][key] = {"type": "FeatureCollection", "features": feats}
    try:
        q = db.execute('select styleQML from layer_styles where f_table_name=? and useAsDefault=1', (table,)).fetchone()[0]
        r = ET.fromstring(q); syms = {s.get('name'): symcolor(s) for s in r.iter('symbol')}
        cats = {c.get('value'): syms.get(c.get('symbol')) for c in r.iter('category')}
        out['styles'][key] = cats if cats else next(iter(syms.values()))
    except Exception: out['styles'][key] = None
open('data/data.js', 'w').write('const GH=' + json.dumps(out, separators=(',', ':')) + ';')
print({k: len(v['features']) for k, v in out['layers'].items()}, 'written to data/data.js')
