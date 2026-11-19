"""Área de segurança do Instagram (Reels/Stories, 1080x1920) — padrão LeadScale.

Uso:
  python videos/safe_zone.py                      # gera as guias PNG em videos/guias/
  python videos/safe_zone.py checar video.mp4     # gera video_checagem.mp4 com a guia por cima
  python videos/safe_zone.py checar video.mp4 --anuncio

As guias são só para conferência/edição: NUNCA exporte o vídeo final com elas.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

LARGURA, ALTURA = 1080, 1920

# Margens reservadas (px) — tudo que é importante fica FORA delas.
MARGENS = {
    # Reels/Stories orgânico
    "organico": {"topo": 250, "base": 480, "esquerda": 60, "direita": 150},
    # Anúncio (Meta Ads em Reels/Stories): 14% topo, 35% base, 6% laterais
    "anuncio": {"topo": 270, "base": 670, "esquerda": 65, "direita": 150},
}

# Recorte da grade do perfil (3:4 centralizado): capa/1º frame precisa caber aqui.
GRADE_TOPO, GRADE_BASE = 240, 1680


def area_segura(modo="organico"):
    m = MARGENS[modo]
    return (m["esquerda"], m["topo"], LARGURA - m["direita"], ALTURA - m["base"])


def gerar_guia(modo, caminho):
    img = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = area_segura(modo)
    vermelho = (255, 40, 40, 110)
    d.rectangle([0, 0, LARGURA, y0], fill=vermelho)                 # topo
    d.rectangle([0, y1, LARGURA, ALTURA], fill=vermelho)            # base
    d.rectangle([0, y0, x0, y1], fill=vermelho)                     # esquerda
    d.rectangle([x1, y0, LARGURA, y1], fill=vermelho)               # direita (botões)
    d.rectangle([x0, y0, x1, y1], outline=(0, 255, 120, 255), width=4)
    # linhas do recorte da grade 3:4
    for y in (GRADE_TOPO, GRADE_BASE):
        for x in range(0, LARGURA, 40):
            d.line([x, y, x + 20, y], fill=(255, 220, 0, 255), width=3)
    d.text((x0 + 12, y0 + 10), f"AREA SEGURA ({modo})", fill=(0, 255, 120, 255))
    d.text((x1 + 8, y0 + 10), "BOTOES", fill=(255, 255, 255, 255))
    d.text((20, y1 + 12), "LEGENDA / @ / AUDIO", fill=(255, 255, 255, 255))
    d.text((20, 20), "PERFIL / TOPO", fill=(255, 255, 255, 255))
    img.save(caminho)


def gerar_guias():
    pasta = os.path.join(os.path.dirname(__file__), "guias")
    os.makedirs(pasta, exist_ok=True)
    for modo in MARGENS:
        caminho = os.path.join(pasta, f"guia_{modo}_1080x1920.png")
        gerar_guia(modo, caminho)
        print(caminho, "->", area_segura(modo))


def checar(video, modo):
    guia = os.path.join(os.path.dirname(__file__), "guias", f"guia_{modo}_1080x1920.png")
    if not os.path.exists(guia):
        gerar_guias()
    saida = os.path.splitext(video)[0] + "_checagem.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", video, "-i", guia, "-filter_complex",
        f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease,"
        f"pad={LARGURA}:{ALTURA}:(ow-iw)/2:(oh-ih)/2[v];[v][1:v]overlay=0:0",
        "-c:a", "copy", saida,
    ], check=True)
    print("Prévia de checagem:", saida)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "checar":
        checar(args[1], "anuncio" if "--anuncio" in args else "organico")
    else:
        gerar_guias()
