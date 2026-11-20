# LeadScale Geodados

Dados públicos preparados para os estudos de viabilidade e geomarketing da LeadScale.
O IBGE e o OpenStreetMap não abrem a partir do ambiente do Claude, então as automações (GitHub Actions) baixam os arquivos oficiais e guardam aqui um resumo por estado.

Automações (aba Actions, botão "Run workflow", informar a sigla do estado):
- **1 - Catalogar arquivos do IBGE**: lista o que o IBGE publica e baixa os dicionários de variáveis.
- **2 - Processar estado (setores censitários)**: população por idade e sexo, tipo de moradia e renda por setor censitário; classe social e PEA por área de ponderação. Fonte: IBGE, Censo 2022.
- **3 - Camada de rua (OpenStreetMap)**: vias com classe e nome, cruzamentos, comércio e serviços, paradas de transporte e polos (shopping, supermercado, hospital). Fonte: © colaboradores do OpenStreetMap, licença ODbL. Rodar de novo a cada 3 a 6 meses para atualizar.

Estados processados: SP e BA (setores); SP (camada de rua).

## Duas perguntas, duas ferramentas

**1. A região sustenta a loja?** (quem mora perto)

```
python tools/perfil_raio.py SP <lat> <lon> <raio_km> --publico m:20-59
```

População, domicílios, faixa etária, público-alvo, casa x apartamento, renda do responsável, PEA estimada e classe social estimada (A++ a E) do raio.

**2. Qual é o melhor ponto dentro da região?** (onde a loja fica na malha da cidade)

```
python tools/perfil_ponto.py SP --ponto "Rua X, 100" <lat> <lon> --ponto "Av. Y, 200" <lat> <lon> \
                                --ref "Unidade de referência" <lat> <lon> [--google comercio.json]
```

Via em frente e sua classe, avenida principal mais próxima, esquina, comércio a 100/200/400 m, comércio na própria rua, paradas de ônibus, distância a shopping e supermercado, e a **nota do ponto** (0 a 10):

| Bloco | Peso | O que mede |
|---|---|---|
| Via e visibilidade | 35% | avenida principal ou secundária = 10; via coletora = 8; rua residencial = 3, subindo para 5 a 8 se ficar a até 200 m de avenida ou se a própria rua for comercial; esquina soma 0,75 a 1,5 |
| Comércio em volta | 30% | lojas e serviços a até 200 m e ao longo da rua do ponto (escala log, 40 lojas a 200 m = 10) |
| Polos | 20% | shopping a até 500 m = 10, 1 km = 8, 1,5 km = 6; supermercado a até 200 m = 6 |
| Transporte | 15% | paradas de ônibus a até 400 m: nenhuma = 2, 1 = 5, 2 a 3 = 7, 4 ou mais = 10 |

Calibração (nov/2026, unidades Gless): Aquarius 8,4, Jacareí 7,2 (com Google Maps), Vila Mariana 6,1. Teste no Jardim Satélite (SJC): Av. Cidade Jardim 8,3, Rua Virgem 7,6, Rua Crater 4,4, igual à avaliação feita em campo pela rede.

**Comércio pelo Google Maps.** O OpenStreetMap tem poucas lojas cadastradas em parte do Brasil (o script avisa em `cobertura_osm`). Nesses casos, rodar buscas no Google Maps em volta do ponto, salvar os lugares num JSON e usar:

```
python tools/comercio_google.py <lat> <lon> "<nome do ponto>" "<rua do ponto>" lugares.json comercio.json
```

Depois passar `--google comercio.json` ao `perfil_ponto.py`. Cada busca do Google devolve no máximo 10 lugares, então a contagem é um piso; a soma de avaliações a até 200 m é um indicador indireto de movimento.

O que nenhuma base pública mede e precisa de olho humano: fachada, letreiro, aparência da rua, estacionamento, movimento real de pedestres. Ver Street View e, quando o ponto for decisivo, contar o fluxo no local.
