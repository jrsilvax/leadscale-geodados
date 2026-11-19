# Padrão de vídeos LeadScale — Área de segurança do Instagram

Vale para **todo** vídeo vertical (Reels, Stories, anúncios). Texto, logo, rosto, número,
legenda e CTA ficam **sempre dentro da área segura**, nunca atrás dos botões, do @ ou da legenda do app.

## Formato

- 1080 × 1920 px, proporção 9:16, 30 fps, H.264 + AAC.
- Fundo/imagem pode ocupar a tela inteira; só o **conteúdo importante** respeita a área segura.

## Área segura (conteúdo importante só aqui)

| Zona reservada | Orgânico (Reels/Stories) | Anúncio (Meta Ads) | O que o Instagram põe ali |
|---|---|---|---|
| Topo | 250 px | 270 px (14%) | nome do perfil, "Reels", câmera, barra de progresso do Stories |
| Base | 480 px | 670 px (35%) | @, legenda do post, áudio, botão "Saiba mais"/CTA do anúncio |
| Direita | 150 px | 150 px | curtir, comentar, compartilhar, salvar, áudio |
| Esquerda | 60 px | 65 px | respiro de borda |

**Retângulo seguro (x0, y0 → x1, y1):**
- Orgânico: **60, 250 → 930, 1440** (870 × 1190 px)
- Anúncio: **65, 270 → 930, 1250** (865 × 980 px)

Na dúvida se o vídeo vai virar anúncio, use o retângulo de **anúncio** (serve para os dois).

## Regras práticas

1. **Legendas faladas**: centralizadas em x = 495 (centro da área segura, não da tela), no máximo
   2 linhas, com a base da legenda em y ≤ 1400 (orgânico) / y ≤ 1220 (anúncio).
2. **Título/gancho dos 3 primeiros segundos**: entre y = 300 e y = 700.
3. **Logo / @ da LeadScale**: dentro da área segura, nunca no canto inferior direito.
4. **CTA final** ("link na bio", "chama no direct"): no meio da área segura, nunca embaixo.
5. **Rosto do apresentador**: olhos por volta de y ≈ 650–800; o rosto não pode ficar sob os botões da direita.
6. **Capa / 1º frame**: o perfil corta a capa em 3:4 (y 240 → 1680). Título da capa dentro desse
   recorte **e** da área segura.
7. Nada de texto encostado na borda: mínimo de 60 px de qualquer lateral.

## Ferramentas

- Guias para colocar como camada no editor (CapCut, Premiere, Canva) — **desligar antes de exportar**:
  - `videos/guias/guia_organico_1080x1920.png`
  - `videos/guias/guia_anuncio_1080x1920.png`
  - Vermelho = zona proibida; verde = área segura; tracejado amarelo = recorte da capa no perfil.
- Checar um vídeo pronto (gera `<video>_checagem.mp4` com a guia por cima):
  ```
  python videos/safe_zone.py checar meu_video.mp4            # orgânico
  python videos/safe_zone.py checar meu_video.mp4 --anuncio  # anúncio
  ```
- Regerar as guias: `python videos/safe_zone.py`

## Checklist antes de publicar

- [ ] 1080 × 1920, 9:16
- [ ] Nenhum texto/logo/rosto na zona vermelha (rodou a checagem)
- [ ] Legenda ≤ 2 linhas e acima da zona da base
- [ ] Capa legível no recorte 3:4 do perfil
- [ ] Guia desligada no export final
