"""Perfil de um raio a partir de data/setores_<UF>.csv.gz e data/areas_ponderacao_<UF>.csv.

Uso: python tools/perfil_raio.py SP -20.547263 -47.399299 1.5 [--publico m:20-59]

Método: entram os setores cujo ponto interno (representative point) cai no raio.
Classe social é ESTIMATIVA: renda domiciliar per capita lognormal por área de ponderação
(média e mediana do IBGE), deslocada pela renda do responsável de cada setor e multiplicada
pelos moradores por domicílio; faixas iguais às do Geofusion, em salários mínimos.
PEA é ESTIMATIVA: taxa da área de ponderação aplicada à população de 14+ de cada setor.
Valores de renda em R$ de 2022 (referência do Censo).
"""
import sys, json, math
import numpy as np, pandas as pd
from math import erf, sqrt, log

uf, lat0, lon0, raio = sys.argv[1].upper(), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
publico = "m:20-59"
if "--publico" in sys.argv: publico = sys.argv[sys.argv.index("--publico") + 1]
s = pd.read_csv(f"data/setores_{uf}.csv.gz", dtype={"cd_setor": str, "cd_mun": str, "cd_area_ponderacao": str})
A = pd.read_csv(f"data/areas_ponderacao_{uf}.csv", dtype={"cd_area_ponderacao": str, "cd_mun": str}).set_index("cd_area_ponderacao")

def dist(la, lo):
    p1, p2 = np.radians(lat0), np.radians(la); dl = np.radians(lo - lon0)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(h))

s["dist_km"] = dist(s.lat, s.lon)
r = s[s.dist_km <= raio].copy()
n = lambda c: float(r[c].fillna(0).sum())
FX = ["0_4","5_9","10_14","15_19","20_24","25_29","30_39","40_49","50_59","60_69","70m"]
LIM = {"0_4":(0,4),"5_9":(5,9),"10_14":(10,14),"15_19":(15,19),"20_24":(20,24),"25_29":(25,29),"30_39":(30,39),"40_49":(40,49),"50_59":(50,59),"60_69":(60,69),"70m":(70,200)}
sexo, faixa = publico.split(":"); ini, fim = map(int, faixa.split("-"))
pref = {"m": ["m_"], "h": ["h_"], "t": ["t_"]}[sexo]
alvo = sum(n(pref[0] + k) for k in FX if LIM[k][0] >= ini and LIM[k][1] <= fim)

out = {"uf": uf, "centro": [lat0, lon0], "raio_km": raio, "setores": len(r),
       "area_setores_km2": round(n("area_km2"), 2), "populacao": n("pop"), "domicilios_ocupados": n("dom_ocupados"),
       "populacao_com_idade_divulgada": n("pop_demo"), "homens": n("homens"), "mulheres": n("mulheres"),
       "publico_alvo": {"definicao": publico, "pessoas": alvo},
       "faixa_etaria": {k: n("t_" + k) for k in FX},
       "mulheres_por_faixa": {k: n("m_" + k) for k in FX},
       "tipo_domicilio": {"casa": n("dom_casa"), "casa_condominio": n("dom_casa_condominio"), "apartamento": n("dom_apartamento")},
       "areas_ponderacao": r.cd_area_ponderacao.value_counts().to_dict(),
       "bairros": r.nm_bairro.value_counts().to_dict()}

w = r.resp_dppo.fillna(0)
out["renda_resp_media_2022"] = round(float((r.renda_resp_media * w).sum() / w[r.renda_resp_media.notna()].sum()), 2)

r["pop14"] = sum(r["t_" + k].fillna(0) for k in FX[3:]) + 0.2 * r.t_10_14.fillna(0)
r["pea"] = r.pop14 * r.cd_area_ponderacao.map(A.forca_trabalho / A.pop14)
r["ocup"] = r.pop14 * r.cd_area_ponderacao.map(A.ocupados / A.pop14)
out["pea_estimada"] = {"pop_14_mais": round(float(r.pop14.sum())), "forca_trabalho": round(float(r.pea.sum())), "ocupados": round(float(r.ocup.sum()))}

aps = s[s.cd_area_ponderacao.isin(r.cd_area_ponderacao.dropna().unique())]
rap = aps.groupby("cd_area_ponderacao").apply(lambda x: (x.renda_resp_media * x.resp_dppo).sum() / x.resp_dppo[x.renda_resp_media.notna()].sum())
CLS = ["E","D","C2","C1","B2","B1","A+","A++"]; LIM26 = [0,1600,1900,3600,6200,10800,21000,36500]
edges = [l / 1621 * 1212 for l in LIM26] + [1e12]
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
acc = np.zeros(8); tot = 0; massa = 0
for _, x in r.iterrows():
    ap, d = x.cd_area_ponderacao, x.dom_ocupados
    if pd.isna(d) or d == 0 or pd.isna(x.renda_resp_media) or ap not in A.index: continue
    mean, med = A.loc[ap, "renda_pc_media"], A.loc[ap, "renda_pc_mediana"]
    sig = sqrt(max(2 * log(mean / med), 0.05))
    mu = log(med * (x.renda_resp_media / rap[ap]) * (x.mor_por_dom if not pd.isna(x.mor_por_dom) else 2.8))
    p = [Phi((log(edges[i + 1]) - mu) / sig) - (Phi((log(edges[i]) - mu) / sig) if edges[i] > 0 else 0) for i in range(8)]
    acc += np.array(p) * d; tot += d; massa += d * math.exp(mu + sig * sig / 2)
out["classe_estimada_pct_domicilios"] = {c: round(float(v / tot * 100), 1) for c, v in zip(CLS, acc)} if tot else None
out["renda_domiciliar_media_estimada_2022"] = round(massa / tot) if tot else None
print(json.dumps(out, ensure_ascii=False, indent=1))
