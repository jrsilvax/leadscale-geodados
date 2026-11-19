# LeadScale Geodados

Dados públicos do IBGE (Censo 2022) preparados para os estudos de viabilidade e geomarketing da LeadScale.
O IBGE não abre a partir do ambiente do Claude, então as automações (GitHub Actions) baixam os arquivos oficiais e guardam aqui um resumo por estado.

- **1 - Catalogar arquivos do IBGE**: lista o que o IBGE publica e baixa os dicionários de variáveis.
- **2 - Processar por estado** (próxima etapa): população por idade e sexo, tipo de moradia e renda por setor censitário; classe social e PEA por área de ponderação.

Fonte de todos os dados: IBGE, Censo Demográfico 2022.

## Padrão de vídeos

Todo vídeo para Instagram segue [videos/PADRAO_VIDEOS_INSTAGRAM.md](videos/PADRAO_VIDEOS_INSTAGRAM.md) (área de segurança, guias e checagem).

## Como usar num estudo

```
python tools/perfil_raio.py SP <lat> <lon> <raio_km> --publico m:20-59
```

Devolve população, domicílios, faixa etária, público-alvo, casa x apartamento, renda do responsável, PEA estimada e classe social estimada (A++ a E) do raio. Para outro estado, rode antes a automação "2 - Processar estado" com a sigla.
