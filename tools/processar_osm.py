"""Camada de rua (OpenStreetMap) por estado, para a nota do ponto.

Uso (na automação): python tools/processar_osm.py <UF> <arquivo_filtrado.osm.pbf>

Lê um extrato do OpenStreetMap já recortado e filtrado (ver .github/workflows/processar_osm.yml)
e grava, em blocos de 0,2 grau (cerca de 22 km), em data/osm/<UF>/:
  <bloco>_vias.csv.gz   uma linha por trecho de via: classe, nome, geometria (polyline, precisão 1e-5)
  <bloco>_pontos.csv.gz pontos de interesse, paradas de transporte e cruzamentos de vias
Grupos de ponto: varejo, alimentacao, servicos, beleza, fitness, ensino, saude, polo, transporte, cruzamento.
"""
import sys, os, csv, gzip, math
from collections import defaultdict
import osmium

UF, PBF = sys.argv[1].upper(), sys.argv[2]
OUT = f"data/osm/{UF}"
os.makedirs(OUT, exist_ok=True)
TILE = 0.2
VIAS = {"motorway": 1, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4, "unclassified": 5,
        "residential": 6, "living_street": 7, "pedestrian": 7,
        "motorway_link": 1, "trunk_link": 1, "primary_link": 2, "secondary_link": 3, "tertiary_link": 4}
IGNORAR = {"parking", "parking_space", "bench", "waste_basket", "waste_disposal", "toilets", "drinking_water",
           "bicycle_parking", "motorcycle_parking", "vending_machine", "recycling", "post_box", "telephone",
           "shelter", "clock", "fountain", "parking_entrance", "grave_yard", "hunting_stand", "loading_dock",
           "charging_station", "atm", "taxi", "bbq", "watering_place", "water_point", "letter_box", "lounger"}

def tile(lat, lon):
    return f"{int((lat + 90) // TILE)}_{int((lon + 180) // TILE)}"

def enc(coords):
    out, pla, plo = [], 0, 0
    for la, lo in coords:
        a, b = int(round(la * 1e5)), int(round(lo * 1e5))
        for v in (a - pla, b - plo):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63)); v >>= 5
            out.append(chr(v + 63))
        pla, plo = a, b
    return "".join(out)

def grupo(t):
    sh, am, le = t.get("shop"), t.get("amenity"), t.get("leisure")
    hw, pt, rw = t.get("highway"), t.get("public_transport"), t.get("railway")
    if hw == "bus_stop" or pt in ("platform", "station", "stop_position") or am == "bus_station" or rw in ("station", "subway_entrance", "halt", "tram_stop"):
        return "transporte", hw or pt or am or rw
    if sh in ("mall", "supermarket", "department_store", "wholesale") or am in ("marketplace", "hospital") or t.get("building") == "retail" and t.get("name"):
        return "polo", sh or am or "retail"
    if sh in ("beauty", "hairdresser", "cosmetics", "perfumery", "nails") or am == "beauty":
        return "beleza", t.get("beauty") or sh
    if sh:
        return "varejo", sh
    if am in ("restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "food_court", "biergarten"):
        return "alimentacao", am
    if le in ("fitness_centre", "sports_centre") or am == "gym":
        return "fitness", le or am
    if am in ("school", "university", "college", "kindergarten", "language_school", "driving_school"):
        return "ensino", am
    if am in ("clinic", "dentist", "doctors", "pharmacy", "veterinary") or t.get("healthcare"):
        return "saude", am or t.get("healthcare")
    if am in ("bank", "post_office", "townhall", "courthouse", "police", "fuel", "car_wash", "place_of_worship", "community_centre", "theatre", "cinema", "library", "coworking_space"):
        return "servicos", am
    if t.get("office") or t.get("craft"):
        return "servicos", t.get("office") or t.get("craft")
    if t.get("tourism") == "hotel":
        return "servicos", "hotel"
    if am and am not in IGNORAR:
        return "servicos", am
    return None, None

class Contagem(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.n = defaultdict(int)
    def way(s, w):
        if w.tags.get("highway") in VIAS:
            for nd in w.nodes: s.n[nd.ref] += 1

class Coleta(osmium.SimpleHandler):
    def __init__(s, cont):
        super().__init__(); s.cont = cont
        s.vias = defaultdict(list); s.pts = defaultdict(list); s.cruz = {}
    def ponto(s, lat, lon, t, oid):
        g, tp = grupo(t)
        if g:
            s.pts[tile(lat, lon)].append((round(lat, 6), round(lon, 6), g, tp, t.get("name", ""), t.get("brand", ""), oid))
    def node(s, n):
        if len(n.tags) and n.location.valid():
            s.ponto(n.location.lat, n.location.lon, n.tags, f"n{n.id}")
    def way(s, w):
        t = w.tags; hw = t.get("highway")
        if hw in VIAS:
            cs = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
            if len(cs) < 2: return
            nome = t.get("name", "")
            for i in range(0, len(cs) - 1, 39):
                ch = cs[i:i + 40]
                s.vias[tile(*ch[0])].append((w.id, VIAS[hw], hw, nome, enc(ch)))
            for nd in w.nodes:
                if s.cont.get(nd.ref, 0) >= 2 and nd.location.valid():
                    c = s.cruz.setdefault(nd.ref, [nd.lat, nd.lon, set(), 9])
                    if nome: c[2].add(nome)
                    c[3] = min(c[3], VIAS[hw])
        elif w.is_closed() and len(w.nodes) > 2 and len(t):
            cs = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
            if cs:
                s.ponto(sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs), t, f"w{w.id}")

print("contando nós das vias...", flush=True)
c = Contagem(); c.apply_file(PBF)
cont = {k: v for k, v in c.n.items() if v >= 2}; del c
print(f"{len(cont)} nós compartilhados; coletando...", flush=True)
h = Coleta(cont); h.apply_file(PBF, locations=True, idx="flex_mem")
for ref, (la, lo, nomes, cmin) in h.cruz.items():
    if len(nomes) >= 2:
        h.pts[tile(la, lo)].append((round(la, 6), round(lo, 6), "cruzamento", str(cmin), "|".join(sorted(nomes))[:200], "", f"n{ref}"))

for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
nv = npnt = 0
for k, rows in h.vias.items():
    with gzip.open(f"{OUT}/{k}_vias.csv.gz", "wt", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["way_id", "classe", "tipo", "nome", "geom"]); wr.writerows(rows); nv += len(rows)
for k, rows in h.pts.items():
    with gzip.open(f"{OUT}/{k}_pontos.csv.gz", "wt", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["lat", "lon", "grupo", "tipo", "nome", "marca", "osm_id"]); wr.writerows(rows); npnt += len(rows)
print(f"{UF}: {nv} trechos de via, {npnt} pontos, {len(set(h.vias) | set(h.pts))} blocos", flush=True)
