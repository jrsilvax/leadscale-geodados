"""Lista os arquivos do Censo 2022 no FTP do IBGE e baixa só os dicionários
(arquivos pequenos), convertidos para CSV, para planejar o processamento."""
import csv, os, re, sys, urllib.request, urllib.parse, io, zipfile

RAIZES = [
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/",
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/",
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Microdados_e_Areas_de_Ponderacao/",
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/",
]
PEQUENOS = re.compile(r"(dicion|layout|composi|leia|readme|atualiza)", re.I)
OUT = "catalogo"
os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def listar(url, prof=0, max_prof=4):
    try:
        html = get(url).decode("utf-8", "replace")
    except Exception as e:
        yield (url, "ERRO", str(e)); return
    for href, resto in re.findall(r'<a href="([^"?][^"]*)">[^<]*</a>\s*([^\n<]*)', html):
        if href.startswith("/") or href.startswith(".."):
            continue
        full = urllib.parse.urljoin(url, href)
        if href.endswith("/"):
            if prof < max_prof:
                yield from listar(full, prof + 1, max_prof)
        else:
            yield (full, "arquivo", " ".join(resto.split()))

linhas = []
for raiz in RAIZES:
    for item in listar(raiz):
        linhas.append(item)
        print(*item, flush=True)

with open(f"{OUT}/arquivos_ibge.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["url", "tipo", "data_tamanho"]); w.writerows(linhas)

def salvar_xlsx(nome, dados):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
    for ws in wb.worksheets:
        alvo = f"{OUT}/dic/{nome}__{re.sub(r'[^A-Za-z0-9]+','_',ws.title)}.csv"
        with open(alvo, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                if any(c is not None for c in row):
                    w.writerow(["" if c is None else c for c in row])

os.makedirs(f"{OUT}/dic", exist_ok=True)
for url, tipo, _ in linhas:
    nome = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    if tipo != "arquivo" or not PEQUENOS.search(nome):
        continue
    try:
        dados = get(url)
    except Exception as e:
        print("falhou", url, e); continue
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", nome)
    if nome.lower().endswith(".xlsx"):
        salvar_xlsx(base, dados)
    elif nome.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            for n in z.namelist():
                if n.lower().endswith(".xlsx"):
                    salvar_xlsx(re.sub(r"[^A-Za-z0-9._-]+", "_", n), z.read(n))
                elif n.lower().endswith((".csv", ".txt")) and z.getinfo(n).file_size < 5_000_000:
                    open(f"{OUT}/dic/{re.sub(r'[^A-Za-z0-9._-]+','_',n)}", "wb").write(z.read(n))
    elif nome.lower().endswith((".csv", ".txt")) and len(dados) < 5_000_000:
        open(f"{OUT}/dic/{base}", "wb").write(dados)
print("ok", len(linhas), "itens")
