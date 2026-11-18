"""Etapa 2: gera data/setores_<UF>.csv.gz com um setor censitário por linha.

Fontes (IBGE, Censo 2022):
- malha de setores da UF (gpkg): centroide, área, município, bairro
- agregados por setor: básico, demografia (sexo x idade), características do domicílio 1 (casa/apto)
- renda do responsável por setor
- composição das áreas de ponderação (setor -> área de ponderação)
Também baixa as tabelas por área de ponderação (amostra) e guarda uma amostra delas
em catalogo/ap/ para mapear classe de renda e PEA na etapa seguinte.
"""
import csv, io, os, re, sys, zipfile, urllib.request
import pandas as pd

UF = sys.argv[1].upper()
UF_COD = {'RO':11,'AC':12,'AM':13,'RR':14,'PA':15,'AP':16,'TO':17,'MA':21,'PI':22,'CE':23,'RN':24,
          'PB':25,'PE':26,'AL':27,'SE':28,'BA':29,'MG':31,'ES':32,'RJ':33,'SP':35,'PR':41,'SC':42,
          'RS':43,'MS':50,'MT':51,'GO':52,'DF':53}[UF]
FTP = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
GEO = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/"
os.makedirs("data", exist_ok=True); os.makedirs("catalogo/ap", exist_ok=True); os.makedirs("tmp", exist_ok=True)

def baixar(url, destino):
    if os.path.exists(destino): return destino
    print("baixando", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(destino, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    return destino

def url_do_catalogo(padrao):
    for row in csv.DictReader(open("catalogo/arquivos_ibge.csv", encoding="utf-8")):
        if re.search(padrao, urllib.parse.unquote(row["url"])):
            return row["url"]
    raise SystemExit(f"não achei no catálogo: {padrao}")

import urllib.parse

def ler_agregado(padrao, colunas):
    url = url_do_catalogo(padrao)
    z = zipfile.ZipFile(baixar(url, "tmp/" + url.rsplit("/", 1)[-1]))
    nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    raw = z.open(nome).read(4096).decode("latin-1")
    sep = ";" if raw.count(";") > raw.count(",") else ","
    partes = []
    for enc in ("utf-8", "latin-1"):
        try:
            it = pd.read_csv(z.open(nome), sep=sep, dtype=str, chunksize=200000, encoding=enc)
            partes = []
            for ch in it:
                ch.columns = [c.replace("\ufeff", "").strip().strip('"').upper() for c in ch.columns]
                if "CD_SETOR" not in ch.columns:
                    alvo = [c for c in ch.columns if "SETOR" in c] or [ch.columns[0]]
                    print("coluna do setor:", alvo[0], "| colunas:", list(ch.columns)[:8], flush=True)
                    ch = ch.rename(columns={alvo[0]: "CD_SETOR"})
                ch = ch[ch["CD_SETOR"].notna()]
                ch = ch[ch["CD_SETOR"].str.startswith(str(UF_COD))]
                keep = ["CD_SETOR"] + [c for c in colunas if c in ch.columns]
                partes.append(ch[keep])
            break
        except UnicodeDecodeError:
            continue
    df = pd.concat(partes)
    faltando = [c for c in colunas if c not in df.columns]
    if faltando: print("AVISO: colunas ausentes em", padrao, faltando)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")  # 'X' (sigilo) vira vazio
    print(padrao, len(df), "setores", flush=True)
    return df

# 1) malha da UF
import geopandas as gpd
gpkg = baixar(GEO + f"setores/gpkg/UF/{UF}/{UF}_setores_CD2022.gpkg", f"tmp/{UF}_setores.gpkg")
g = gpd.read_file(gpkg)
g.columns = [c.upper() if c != "geometry" else c for c in g.columns]
pts = g.geometry.representative_point()
malha = pd.DataFrame({
    "cd_setor": g["CD_SETOR"].astype(str).str.replace(r"\D", "", regex=True),
    "cd_mun": g.get("CD_MUN"), "nm_mun": g.get("NM_MUN"),
    "cd_bairro": g.get("CD_BAIRRO"), "nm_bairro": g.get("NM_BAIRRO"),
    "nm_dist": g.get("NM_DIST"), "situacao": g.get("SITUACAO"), "cd_tipo": g.get("CD_TIPO"),
    "lat": pts.y.round(6), "lon": pts.x.round(6),
})
if "AREA_KM2" in g.columns:
    malha["area_km2"] = pd.to_numeric(g["AREA_KM2"], errors="coerce")
else:
    malha["area_km2"] = (g.to_crs(5880).area / 1e6).round(4)
print("malha", len(malha), flush=True)

# 2) agregados
basico = ler_agregado(r"Agregados_por_Setor_csv/Agregados_por_setores_basico_BR", ["V0001", "V0002", "V0005", "V0007"])
demo = ler_agregado(r"Agregados_por_Setor_csv/Agregados_por_setores_demografia_BR", [f"V0{n}" for n in range(1006, 1042)])
dom1 = ler_agregado(r"Agregados_por_Setor_csv/Agregados_por_setores_caracteristicas_domicilio1_BR", ["V00047", "V00048", "V00049"])
renda = ler_agregado(r"Agregados_por_setores_renda_responsavel_BR_\d+_csv", ["V06001", "V06002", "V06004", "V06006"])

ren = {"V0001": "pop", "V0002": "dom_total", "V0005": "mor_por_dom", "V0007": "dom_ocupados",
       "V00047": "dom_casa", "V00048": "dom_casa_condominio", "V00049": "dom_apartamento",
       "V06001": "resp_dppo", "V06002": "mor_dppo", "V06004": "renda_resp_media", "V06006": "renda_resp_mediana"}
faixas = ["0_4","5_9","10_14","15_19","20_24","25_29","30_39","40_49","50_59","60_69","70m"]
ren["V01006"] = "pop_demo"; ren["V01007"] = "homens"; ren["V01008"] = "mulheres"
for i, fx in enumerate(faixas):
    ren[f"V0{1009+i}"] = f"h_{fx}"; ren[f"V0{1020+i}"] = f"m_{fx}"
for i, fx in enumerate(faixas):
    ren[f"V0{1031+i}"] = f"t_{fx}"

df = malha
for parte in (basico, demo, dom1, renda):
    parte = parte.rename(columns={"CD_SETOR": "cd_setor"})
    parte["cd_setor"] = parte["cd_setor"].str.replace(r"\D", "", regex=True)
    df = df.merge(parte, on="cd_setor", how="left")
df = df.rename(columns=ren)

# 3) área de ponderação
comp = pd.read_csv("catalogo/dic/Composi_o_das_reas_de_Pondera_o.xlsx__Planilha1.csv", dtype=str)
comp.columns = ["cd_setor", "cd_mun_ap", "cd_area_ponderacao", "nm_mun_ap"]
df = df.merge(comp[["cd_setor", "cd_area_ponderacao"]], on="cd_setor", how="left")

df.to_csv(f"data/setores_{UF}.csv.gz", index=False, compression="gzip")
print("gravado", f"data/setores_{UF}.csv.gz", len(df), "setores; pop total", df["pop"].sum(), flush=True)

# 4) tabelas por área de ponderação: listar e guardar amostras para a próxima etapa
try:
    url = url_do_catalogo(r"Areas_de_Ponderacao/tabelas_xlsx_")
    z = zipfile.ZipFile(baixar(url, "tmp/tabelas_ap.zip"))
    with open("catalogo/ap/lista_tabelas.txt", "w", encoding="utf-8") as f:
        for i in z.infolist():
            f.write(f"{i.filename}\t{i.file_size}\n")
    import openpyxl
    for n in z.namelist():
        if not n.lower().endswith(".xlsx"): continue
        wb = openpyxl.load_workbook(io.BytesIO(z.read(n)), read_only=True, data_only=True)
        for ws in wb.worksheets:
            base = re.sub(r"[^A-Za-z0-9]+", "_", n.rsplit("/",1)[-1])[:60] + "__" + re.sub(r"[^A-Za-z0-9]+", "_", ws.title)[:30]
            with open(f"catalogo/ap/{base}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                for k, row in enumerate(ws.iter_rows(values_only=True)):
                    if k >= 25: break
                    w.writerow(["" if c is None else c for c in row])
except Exception as e:
    print("AVISO tabelas AP:", e)

# 5) tabelas da amostra por área de ponderação (PEA, renda per capita, escolaridade, ocupação)
TABELAS = {
    "Tab7_1.xlsx": {4: "pop14", 5: "forca_trabalho", 6: "ocupados", 7: "desocupados", 8: "fora_forca"},
    "Tab8_3.xlsx": {4: "pessoas_dpp", 7: "renda_pc_media", 10: "renda_pc_mediana"},
    "Tab8_1.xlsx": {4: "ocupados_com_renda", 5: "renda_trab_media", 6: "renda_trab_mediana"},
    "Tab2_2.xlsx": {4: "pop25", 5: "instr_fund_incompleto", 6: "instr_fund_completo", 7: "instr_medio_completo", 8: "instr_superior"},
    "Tab7_4.xlsx": {4: "ocup_total", 5: "ocup_diretores_gerentes", 6: "ocup_profissionais", 7: "ocup_tecnicos"},
}
try:
    import openpyxl
    z = zipfile.ZipFile("tmp/tabelas_ap.zip")
    ap = None
    for n in z.namelist():
        nome = n.rsplit("/", 1)[-1]
        if nome not in TABELAS: continue
        cols = TABELAS[nome]
        wb = openpyxl.load_workbook(io.BytesIO(z.read(n)), read_only=True, data_only=True)
        linhas = []
        for row in wb.worksheets[0].iter_rows(values_only=True):
            if not row or row[0] is None: continue
            cod = str(row[0]).strip()
            if not (cod.isdigit() and len(cod) == 7 and cod.startswith(str(UF_COD))): continue
            reg = {"cd_mun": cod, "nm_mun": row[1], "cd_area_ponderacao": str(row[2]).strip(), "nm_area": row[3]}
            for i, campo in cols.items():
                v = row[i] if i < len(row) else None
                reg[campo] = 0 if v in ("-", None, "") else v
            linhas.append(reg)
        t = pd.DataFrame(linhas)
        print(nome, len(t), "áreas", flush=True)
        ap = t if ap is None else ap.merge(t.drop(columns=["cd_mun", "nm_mun", "nm_area"]), on="cd_area_ponderacao", how="outer")
    ap.to_csv(f"data/areas_ponderacao_{UF}.csv", index=False)
    print("gravado", f"data/areas_ponderacao_{UF}.csv", len(ap), flush=True)
except Exception as e:
    print("AVISO tabelas AP (dados):", e)
