"""Perfil do PONTO (rua, esquina, comércio, transporte, polos) a partir de data/osm/<UF>/.

Complementa tools/perfil_raio.py: o raio mede a REGIÃO (quem mora perto); este script mede o PONTO
(onde a loja está na malha da cidade). Serve para ordenar candidatos que ficam no mesmo bairro.

Uso:
  python tools/perfil_ponto.py SP --ponto "Rua Virgem, 420" -23.22576 -45.88638 \
                                  --ponto "Rua Crater, 380" -23.22792 -45.89122 \
                                  --ref "Gless Jacareí" -23.26457 -45.94326 --ref "Gless Aquarius" -23.22071 -45.90641
Saída: JSON com os indicadores de cada ponto, a nota do ponto (0 a 10) e, se houver --ref,
cada indicador comparado com a primeira referência (= 100).

Fonte: OpenStreetMap (© colaboradores do OpenStreetMap, licença ODbL). A cobertura de lojas no
OSM é incompleta em parte do Brasil: completar a contagem de comércio com o Google Maps.
"""
import sys, os, json, math, glob
import pandas as pd

ARGS = sys.argv[1:]
UF = ARGS[0].upper()
pontos, refs = [], []
i = 1
while i < len(ARGS):
    if ARGS[i] in ("--ponto", "--ref"):
        (pontos if ARGS[i] == "--ponto" else refs).append((ARGS[i + 1], float(ARGS[i + 2]), float(ARGS[i + 3]))); i += 4
    else:
        i += 1
TILE = 0.2
COMERCIO = {"varejo", "alimentacao", "servicos", "beleza", "fitness", "saude", "polo"}
ARTERIAL = {1, 2, 3}  # rodovia/via expressa, principal, secundária
NOME_CLASSE = {1: "via expressa", 2: "avenida principal", 3: "avenida secundária", 4: "via coletora",
               5: "via sem classificação", 6: "rua residencial", 7: "rua local ou calçadão"}

def dec(s):
    out, i, la, lo = [], 0, 0, 0
    while i < len(s):
        vals = []
        for _ in range(2):
            sh = res = 0
            while True:
                b = ord(s[i]) - 63; i += 1; res |= (b & 0x1f) << sh; sh += 5
                if b < 0x20: break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        la += vals[0]; lo += vals[1]; out.append((la / 1e5, lo / 1e5))
    return out

def carregar(lat, lon, kind):
    a, b = int((lat + 90) // TILE), int((lon + 180) // TILE)
    fs = [f"data/osm/{UF}/{a+da}_{b+db}_{kind}.csv.gz" for da in (-1, 0, 1) for db in (-1, 0, 1)]
    fs = [f for f in fs if os.path.exists(f)]
    if not fs:
        sys.exit(f"Sem dados OSM para {UF} nesta área. Rode a automação '3 - Camada de rua (OpenStreetMap)'.")
    return pd.concat([pd.read_csv(f, keep_default_na=False) for f in fs], ignore_index=True)

def perfil(nome, lat0, lon0):
    kx, ky = math.cos(math.radians(lat0)) * 111320, 110540
    xy = lambda la, lo: ((lo - lon0) * kx, (la - lat0) * ky)
    V = carregar(lat0, lon0, "vias"); P = carregar(lat0, lon0, "pontos")
    P["x"] = (P.lon - lon0) * kx; P["y"] = (P.lat - lat0) * ky; P["d"] = (P.x ** 2 + P.y ** 2) ** 0.5
    P = P[P.d <= 3000]
    segs = []  # (classe, nome, x1, y1, x2, y2)
    for r in V.itertuples():
        cs = [xy(*c) for c in dec(r.geom)]
        if min(abs(x) for x, _ in cs) > 3000 or min(abs(y) for _, y in cs) > 3000: continue
        for (x1, y1), (x2, y2) in zip(cs, cs[1:]):
            segs.append((r.classe, r.nome, x1, y1, x2, y2))
    def dseg(px, py, s):
        _, _, x1, y1, x2, y2 = s; dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L))
        return math.hypot(px - x1 - t * dx, py - y1 - t * dy)
    ds = sorted(((dseg(0, 0, s), s) for s in segs), key=lambda z: z[0])
    frente = ds[0] if ds else None
    def mais_proxima(cond):
        for d, s in ds:
            if cond(s): return {"nome": s[1] or "(sem nome)", "classe": NOME_CLASSE[s[0]], "dist_m": round(d)}
        return None
    arterial = mais_proxima(lambda s: s[0] in ARTERIAL)
    coletora = mais_proxima(lambda s: s[0] <= 4)
    cruz = P[P.grupo == "cruzamento"].sort_values("d")
    esq = cruz.iloc[0] if len(cruz) and cruz.iloc[0].d <= 30 else None
    C = P[P.grupo.isin(COMERCIO)]
    def ao_longo(nome_via, raio=300, faixa=35):
        if not nome_via: return 0
        ss = [s for d, s in ds if s[1] == nome_via and d <= raio + 50]
        if not ss: return 0
        cc = C[C.d <= raio]
        return int(sum(1 for p in cc.itertuples() if min(dseg(p.x, p.y, s) for s in ss) <= faixa))
    T = P[P.grupo == "transporte"]
    def polo(tipos, maxd=3000):
        q = P[(P.grupo == "polo") & (P.tipo.isin(tipos)) & (P.d <= maxd)].sort_values("d")
        return None if q.empty else {"nome": q.iloc[0]["nome"] or q.iloc[0].tipo, "dist_m": round(q.iloc[0].d)}
    out = {
        "ponto": nome, "lat": lat0, "lon": lon0,
        "via_em_frente": None if not frente else {"nome": frente[1][1] or "(sem nome)", "classe": NOME_CLASSE[frente[1][0]],
                                                  "classe_cod": int(frente[1][0]), "dist_m": round(frente[0])},
        "avenida_principal_mais_proxima": arterial,
        "via_coletora_ou_maior_mais_proxima": coletora,
        "esquina": None if esq is None else {"vias": esq["nome"].split("|"), "maior_classe": NOME_CLASSE[int(esq.tipo)], "dist_m": round(esq.d)},
        "comercio": {f"ate_{r}m": int((C.d <= r).sum()) for r in (100, 200, 400)},
        "comercio_200m_por_grupo": C[C.d <= 200].grupo.value_counts().to_dict(),
        "comercio_na_rua_do_ponto_300m": ao_longo(frente[1][1] if frente and frente[0] <= 40 else ""),
        "comercio_na_avenida_mais_proxima_300m": ao_longo(arterial["nome"] if arterial and arterial["dist_m"] <= 400 else ""),
        "transporte": {"paradas_ate_200m": int((T.d <= 200).sum()), "paradas_ate_400m": int((T.d <= 400).sum()),
                       "parada_mais_proxima_m": None if T.empty else round(T.d.min())},
        "polos": {"shopping": polo({"mall"}), "supermercado": polo({"supermarket", "wholesale"}),
                  "loja_de_departamento": polo({"department_store"}), "hospital": polo({"hospital"})},
        "beleza_ate_300m_osm": C[(C.grupo == "beleza") & (C.d <= 300)][["nome", "tipo", "d"]].assign(d=lambda x: x.d.round()).to_dict("records"),
    }
    out["cobertura_osm"] = ("fraca: poucas lojas cadastradas no OpenStreetMap em volta; completar a contagem com o Google Maps "
                            "(tools/comercio_google.py) antes de usar a nota de comércio") if out["comercio"]["ate_400m"] < 10 else "ok"
    out["nota_ponto"] = nota(out)
    return out

def esc(v, pts):  # pts: [(limite, nota)] em ordem; v <= limite -> nota
    for lim, n in pts:
        if v is not None and v <= lim: return n
    return pts[-1][1] if v is None else 0

GOOGLE = {}
if "--google" in ARGS:  # JSON de tools/comercio_google.py: {"nome do ponto": {"ate_200m": n, "na_rua_300m": n}}
    GOOGLE = json.load(open(ARGS[ARGS.index("--google") + 1]))

def nota(o):
    """Nota do ponto, 0 a 10. Pesos: via e visibilidade 35, comércio em volta 30, polos 20, transporte 15.
    Regras absolutas, para servir a um ponto sozinho; calibradas nas unidades Gless (ver SKILL)."""
    g = GOOGLE.get(o["ponto"])
    if g:  # usa a maior contagem entre OSM e Google
        o["comercio"]["ate_200m"] = max(o["comercio"]["ate_200m"], g.get("ate_200m", 0))
        o["comercio_na_rua_do_ponto_300m"] = max(o["comercio_na_rua_do_ponto_300m"], g.get("na_rua_300m", 0))
        o["comercio_fonte"] = "OSM + Google Maps"
    f = o["via_em_frente"]; cls = f["classe_cod"] if f and f["dist_m"] <= 40 else 7
    via = {1: 8, 2: 10, 3: 10, 4: 8, 5: 5, 6: 3, 7: 3}[cls]
    a = o["avenida_principal_mais_proxima"]; dav = a["dist_m"] if a else None
    if cls > 3 and dav is not None:
        via = max(via, esc(dav, [(60, 8), (120, 6.5), (200, 5), (10**9, via)]))
    if cls > 3 and o["comercio_na_rua_do_ponto_300m"] >= 8:  # rua comercial (o OSM costuma classificá-la como residencial)
        via = max(via, 7 if o["comercio_na_rua_do_ponto_300m"] < 15 else 8)
    if o["esquina"]:
        via += 1.5 if o["esquina"]["maior_classe"] in ("avenida principal", "avenida secundária", "via coletora") else 0.75
    via = min(10, via)
    c200, rua = o["comercio"]["ate_200m"], max(o["comercio_na_rua_do_ponto_300m"], o["comercio_na_avenida_mais_proxima_300m"] * (0.8 if cls > 3 else 1))
    com = 0.6 * min(10, 10 * math.log1p(c200) / math.log1p(40)) + 0.4 * min(10, 10 * math.log1p(rua) / math.log1p(20))
    sh = o["polos"]["shopping"]; su = o["polos"]["supermercado"]
    pol = max(esc(sh["dist_m"] if sh else None, [(500, 10), (1000, 8), (1500, 6), (2500, 4), (10**9, 2)]),
              esc(su["dist_m"] if su else None, [(200, 6), (500, 4), (10**9, 2)]))
    tr = {0: 2, 1: 5, 2: 7, 3: 7}.get(o["transporte"]["paradas_ate_400m"], 10)
    total = 0.35 * via + 0.30 * com + 0.20 * pol + 0.15 * tr
    return {"total": round(total, 1), "via_visibilidade": round(via, 1), "comercio_em_volta": round(com, 1),
            "polos": round(pol, 1), "transporte": round(tr, 1)}

res = {"uf": UF, "fonte": "OpenStreetMap (ODbL)", "pontos": [perfil(*p) for p in pontos], "referencias": [perfil(*r) for r in refs]}
if refs:
    b = res["referencias"][0]
    def ind(o): return {"comercio_200m": o["comercio"]["ate_200m"], "comercio_400m": o["comercio"]["ate_400m"],
                        "paradas_400m": o["transporte"]["paradas_ate_400m"], "nota_ponto": o["nota_ponto"]["total"]}
    base = ind(b)
    for o in res["pontos"] + res["referencias"]:
        o["indice_vs_" + b["ponto"]] = {k: (round(v / base[k] * 100) if base[k] else None) for k, v in ind(o).items()}
print(json.dumps(res, ensure_ascii=False, indent=1))
