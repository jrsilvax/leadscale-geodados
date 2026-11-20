"""Contagem de comércio e de avaliações em volta do ponto a partir de buscas no Google Maps.

O OpenStreetMap tem poucas lojas cadastradas em parte do Brasil. Para completar, Claude roda
3 a 6 buscas no Google Maps (places_search) com viés no ponto e raio de 300 m (ex.: "lojas",
"restaurante", "farmácia", "padaria", "clínica", "salão de beleza") e salva todos os resultados num
JSON: lista de {"place_id", "name", "address", "latitude", "longitude", "rating_count"}.

Uso: python tools/comercio_google.py <lat> <lon> "<nome do ponto>" "<nome da rua do ponto>" lugares.json [saida.json]
Saída: comércio a até 100/200/400 m, comércio na rua do ponto (pelo endereço) a até 300 m e a soma de
avaliações a até 200 m (indicador indireto de movimento). Se passar saida.json, acrescenta o ponto nele,
no formato que tools/perfil_ponto.py lê com --google.
Atenção: cada busca do Google devolve no máximo 10 lugares, então a contagem é um piso.
"""
import sys, json, math, os, unicodedata
lat0, lon0, nome, rua, arq = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
saida = sys.argv[6] if len(sys.argv) > 6 else None
norm = lambda t: unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
L = {}
for p in json.load(open(arq)):
    L[p.get("place_id") or p["name"]] = p
def d(p):
    kx = math.cos(math.radians(lat0)) * 111320
    return math.hypot((p["longitude"] - lon0) * kx, (p["latitude"] - lat0) * 110540)
ps = [dict(p, d=d(p)) for p in L.values() if p.get("latitude")]
ps = [p for p in ps if not any(k in (p.get("types") or []) for k in ("route", "political", "street_address", "subpremise"))]
r = norm(rua).replace("rua ", "").replace("avenida ", "").replace("av. ", "").strip()
out = {f"ate_{x}m": sum(1 for p in ps if p["d"] <= x) for x in (100, 200, 400)}
out["na_rua_300m"] = sum(1 for p in ps if p["d"] <= 300 and r and r in norm(p.get("address")))
out["avaliacoes_ate_200m"] = sum(int(p.get("rating_count") or 0) for p in ps if p["d"] <= 200)
out["mais_avaliados_200m"] = [(p["name"], int(p.get("rating_count") or 0), round(p["d"])) for p in sorted(ps, key=lambda p: -(p.get("rating_count") or 0)) if p["d"] <= 200][:8]
print(json.dumps({nome: out}, ensure_ascii=False, indent=1))
if saida:
    tudo = json.load(open(saida)) if os.path.exists(saida) else {}
    tudo[nome] = out
    json.dump(tudo, open(saida, "w"), ensure_ascii=False, indent=1)
