# Dados do projeto Elo (Machine Learning)

**Nenhum dado aqui é simulado.** Todos os arquivos de `brutos/` vêm de fontes públicas, listadas abaixo.
A Open-Meteo entra de duas formas, e nenhuma é medição direta: a **reanálise** (modelo meteorológico combinado com observações) e a **previsão emitida na véspera**, que é a variável central do modelo. A chuva realmente medida vem das estações do INMET.

- **Período:** 01/01/2023 a 31/12/2025.
- **Data da coleta:** 08/11/2026.
- **Como reproduzir:** `python coleta/coletar_tudo.py`, a partir da pasta `ml/`. Os scripts retomam de onde pararam. Do zero, leva cerca de 1 hora (o CGE sozinho, cerca de 40 minutos) e baixa cerca de 380 MB de pacotes do INMET para uma pasta temporária, fora do projeto.
- **Conferência:** `conferencia_coleta.txt` traz as contagens geradas por `coleta/conferir_coleta.py`.

## Situação da coleta

A coleta está completa: as 1.096 datas do período foram consultadas no CGE, com 233 dias com registro, 863 dias sem registro e 2.159 registros no total.

Durante a coleta, o site do CGE passou a responder HTTP 403 depois de cerca de 520 consultas seguidas (pausa de 0,2 s). A coleta foi interrompida, sem gravar nenhuma das datas recusadas. Cerca de 13 minutos depois, o acesso voltou por conta própria, e as 576 datas restantes foram consultadas com o mesmo cliente e pausa de 2 s. O `robots.txt` do site permite o caminho `/v3/`. Por isso, a pausa padrão do script agora é de 2 s, e ele para sozinho após 3 falhas seguidas.

## Fontes

| Arquivo em `brutos/` | Fonte | Link | Período | Unidade |
|---|---|---|---|---|
| `cge_alagamentos_2023_2025.csv` | CGE, Prefeitura de São Paulo | https://www.cgesp.org/v3/alagamentos.jsp | 2023 a 2025 | registro de ponto de alagamento |
| `cge_datas_coletadas.csv` | CGE (controle da coleta) | mesma página | 2023 a 2025 | dia consultado |
| `inmet_horario_sp_2023_2025.csv` | INMET, dados históricos | https://portal.inmet.gov.br/dadoshistoricos | 2023 a 2025 | hora e estação |
| `subprefeituras_geosampa.csv` | GeoSampa, Prefeitura de São Paulo; elevação da Open-Meteo | http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs e https://open-meteo.com/en/docs/elevation-api | camada consultada em 08/11/2026 | subprefeitura (32) |
| `mapa_nomes_cge_geosampa.csv` | construído pela equipe e conferido à mão | não se aplica | não se aplica | nome usado pelo CGE |
| `openmeteo_horario_subprefeituras_2023_2025.csv.gz` | Open-Meteo, Historical Weather API | https://open-meteo.com/en/docs/historical-weather-api | 2023 a 2025 | hora e subprefeitura |
| `openmeteo_previsao_d1_jma_horario_2023_2025.csv.gz` | Open-Meteo, Previous Runs API (modelo JMA GSM) | https://open-meteo.com/en/docs/previous-runs-api | 2023 a 2025 | hora e subprefeitura |

## Uso e licenças

- **Open-Meteo:** licença CC BY 4.0, conforme os termos do serviço (https://open-meteo.com/en/terms). O plano gratuito é para uso não comercial, com limites de 600 chamadas por minuto, 5.000 por hora e 10.000 por dia. Atribuição: *Weather data by Open-Meteo.com*.
- **CGE, INMET e GeoSampa:** dados publicados em portais públicos. Não localizamos uma licença explícita nas respostas consultadas, então o uso aqui é acadêmico e sempre com citação da fonte.
- **Dados pessoais:** não há. Os registros do CGE trazem vias públicas e horários.

## Tratamento e dicionário de colunas

### `cge_alagamentos_2023_2025.csv`

Uma linha por registro publicado pelo CGE, sem remoção de duplicados ou correções. O texto é fiel à página. Um mesmo local pode aparecer mais de uma vez no dia, em horários ou sentidos diferentes.

| Coluna | Descrição |
|---|---|
| `data` | Dia da consulta (AAAA-MM-DD) |
| `zona` | Zona informada pelo CGE (ex.: Zona Leste, Centro) |
| `subprefeitura_cge` | Nome da subprefeitura como o CGE escreve |
| `status_css` | Classe do ícone na página (ex.: `inativo-transitavel`). "Inativo" indica ponto já encerrado |
| `transitavel` | 1 se o ponto era transitável; 0 se intransitável (derivado de `status_css`) |
| `hora_inicio`, `hora_fim` | Início e fim do ponto (HH:MM). `hora_fim` menor que `hora_inicio` pode indicar que o ponto atravessou a meia-noite |
| `local` | Via onde o ponto foi registrado |
| `sentido` | Sentido da via |
| `referencia` | Referência próxima (pode estar vazia) |

**Limitação importante:** o CGE registra o que monitora, principalmente grandes vias. Ausência de registro não prova que não houve alagamento, especialmente em ruas locais da periferia.

**Pontos de atenção encontrados na conferência** (nada foi alterado no arquivo bruto):

- 4 duplicados exatos, todos em Itaim Paulista.
- 118 registros com `hora_fim` menor que `hora_inicio`, que podem ter atravessado a meia-noite. Nenhum horário é inválido ou vazio.
- 5 registros com `referencia` vazia.
- 27 registros com `local` iniciado por `*`: são 9 ruas de São Miguel Paulista, repetidas em 02, 03 e 04/02/2025, todas com o horário 02:00 a 13:59. O CGE não explica o asterisco, e o padrão difere dos demais registros.

### `cge_datas_coletadas.csv`

Uma linha por data consultada com sucesso.

| Coluna | Descrição |
|---|---|
| `data` | Dia consultado |
| `situacao` | `com_registro` ou `sem_registro`. Só é `sem_registro` quando a página traz o texto oficial "Não há registros de alagamentos para essa data." |
| `n_registros` | Quantidade de registros lidos na página |
| `resumo_transitaveis`, `resumo_intransitaveis` | Totais publicados no resumo lateral da página (ativos + inativos) |
| `coletado_em` | Data e hora da consulta |

Falha de rede nunca é tratada como dia sem alagamento: a data fica fora deste arquivo e continua pendente. Cada dia é validado contra os totais da própria página. Dias divergentes vão para `cge_divergencias.csv`, que só existe se houver divergência.

### `inmet_horario_sp_2023_2025.csv`

Medição horária observada nas estações automáticas **A701 (São Paulo - Mirante)** e **A771 (São Paulo - Interlagos)**. Os pacotes anuais do INMET trazem o horário em UTC e usam -9999 para faltante, aqui convertido em célula vazia. O pacote de 2026 foi usado só para completar as 3 últimas horas locais de 31/12/2025. Nenhum valor faltante foi preenchido.

Faltantes de chuva por ano: A701 tem 7,36% em 2023, 0,23% em 2024 e 0,54% em 2025; A771 tem 1,96%, 0,10% e 0,33%. A maior lacuna é da A701, de 24/08 a 12/09/2023 (quase sem dado por 19 dias).

| Coluna | Descrição |
|---|---|
| `estacao` | Código da estação (A701 ou A771) |
| `ts_utc` | Horário UTC informado pelo INMET |
| `ts_local` | Horário de Brasília (UTC-3, fixo no período, pois não há horário de verão desde 2019) |
| `chuva_mm` | Precipitação total na hora (mm) |
| `temp_c` | Temperatura do ar, bulbo seco (°C) |
| `umidade_pct` | Umidade relativa (%) |
| `pressao_hpa` | Pressão atmosférica na estação (mB/hPa) |
| `vento_ms` | Velocidade horária do vento (m/s) |

### `subprefeituras_geosampa.csv`

Limites oficiais das 32 subprefeituras (camada `geoportal:subprefeitura`). O centroide é calculado pela fórmula do polígono, sem biblioteca geoespacial.

| Coluna | Descrição |
|---|---|
| `subprefeitura` | Nome oficial no GeoSampa (chave usada no projeto) |
| `nome_exibicao` | Nome legível, como o CGE escreve quando possível |
| `sigla` | Sigla oficial |
| `regiao5`, `regiao8` | Região da cidade em 5 e 8 grupos |
| `area_km2` | Área em km² (de `qt_area_metro`) |
| `lat_centroide`, `lon_centroide` | Centroide do polígono (graus, EPSG:4326) |
| `elevacao_m` | Elevação no centroide, pela Elevation API da Open-Meteo (modelo digital de terreno de 90 m) |

### `mapa_nomes_cge_geosampa.csv`

Liga cada nome usado pelo CGE ao nome oficial do GeoSampa. A lista foi conferida à mão e fica em `coleta/coletar_subprefeituras.py`. Se surgir um nome novo, o script para e mostra o nome, sem tentar adivinhar. Alguns nomes do CGE são abreviados, por exemplo `Santana` para `SANTANA-TUCURUVI` e `Casa Verde` para `CASA VERDE-LIMAO-CACHOEIRINHA`.

| Coluna | Descrição |
|---|---|
| `subprefeitura_cge` | Nome exatamente como aparece no CGE |
| `subprefeitura` | Nome oficial no GeoSampa |

### `openmeteo_horario_subprefeituras_2023_2025.csv.gz`

**Reanálise, não medição direta.** A Open-Meteo combina observações (estações, aeronaves, boias, radar e satélite) com modelos meteorológicos. Foi usado o padrão *best match*, que junta ECMWF IFS, ERA5 e ERA5-Land. A consulta foi feita no centroide de cada subprefeitura, então várias subprefeituras podem cair no mesmo ponto de grade (ver `conferencia_coleta.txt`).

| Coluna | Descrição |
|---|---|
| `ts_local` | Hora local (America/Sao_Paulo) |
| `subprefeitura` | Nome oficial no GeoSampa |
| `chuva_mm` | Precipitação na hora anterior (mm). Por isso, o dia D somado no notebook vai das 23h de D-1 às 23h de D |
| `umidade_solo_0_7cm` | Umidade do solo de 0 a 7 cm (m³/m³) |
| `grid_lat`, `grid_lon` | Ponto de grade devolvido pela API |

As 32 subprefeituras caem em 19 pontos de grade distintos, então parte delas recebe exatamente a mesma série. Sem faltantes.

### `openmeteo_previsao_d1_jma_horario_2023_2025.csv.gz`

**Previsão real, emitida antes do evento.** Segundo a documentação da Previous Runs API, `precipitation_previous_day1` é o valor previsto 24 horas antes do horário válido. É a variável central do modelo, pois é o que existe de verdade na manhã do dia.

A consulta usa o modelo **JMA GSM**, o único dos consultados com previsão nas janelas testadas de 2023 (janeiro, fevereiro e julho). Os outros modelos (GFS, ICON, ECMWF, GEM, UKMO, Météo-France e o padrão *best match*) só têm dados em algum momento a partir de janeiro de 2024, então não cobrem o treino inteiro. Modelos de maior resolução não foram testados.

O custo da escolha é a resolução. As 32 subprefeituras caem em 3 pontos de grade, e a JMA publica a chuva em blocos de 6 horas: o arquivo traz uma linha por hora, mas todas as horas de um bloco repetem o mesmo valor. Por isso, o notebook chama de `prev_max_bloco` a intensidade do bloco mais chuvoso, e não a trata como um máximo horário.

| Coluna | Descrição |
|---|---|
| `ts_local` | Hora local (America/Sao_Paulo) |
| `subprefeitura` | Nome oficial no GeoSampa |
| `chuva_prevista_d1_mm` | Chuva prevista 24 h antes para aquela hora (mm) |
| `grid_lat`, `grid_lon` | Ponto de grade devolvido pela API |

Cobertura de 100% das horas de 2023 a 2025. A comparação entre previsão, reanálise e INMET fica na seção 3.6 do notebook.

## Comparação com o escopo do grupo

A base citada no escopo não estava disponível, então os dados foram coletados de novo nas fontes públicas. Os números ficaram próximos, mas não idênticos:

| Item | Escopo do grupo | Esta coleta |
|---|---|---|
| Pontos de alagamento | 2.137 | 2.159 |
| Dias na base | 1.055 | 1.096 consultados |
| Dias com alagamento por ano | 68 a 82 | 86 (2023), 68 (2024), 79 (2025) |
| Sé | 335 | 339 |
| Cidade Tiradentes | 5 | 5 |
| % em avenidas | 53% | 54,0% (via iniciada por AV ou AVENIDA; marginais somam mais 4,2%) |

O escopo não informa como chegou aos 1.055 dias.
