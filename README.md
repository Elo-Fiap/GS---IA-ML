# Elo

CitizenTech da Global Solution 2026.2 (FIAP, Engenharia de Software).

## Ficha da CitizenTech

| Campo | Preenchimento |
|---|---|
| Nome | Elo (provisório) |
| Cidade e bairro | São Paulo. Bairro a definir; candidato: Jardim Pantanal |
| Cidadão beneficiado | Moradores de ruas que alagam, por meio da liderança da rua ou do voluntário do núcleo comunitário de Defesa Civil |
| Problema, em uma frase | Durante a chuva forte, quem cuida do bairro não consegue saber quais ruas estão bem, quais precisam de ajuda e quais ficaram em silêncio |
| Como funciona | O aviso oficial chega, a liderança de cada rua responde em um toque, mesmo com internet ruim, e o coordenador vê as ruas sem resposta |
| O que cada parte faz | App: aviso, chamada, plano e registro. API: guarda as chamadas e ordena as ruas em silêncio. ESP32: mede a água e toca o buzzer. **ML: indica o nível de atenção por subprefeitura.** Segurança: evita vazamento do que é digitado. Linux: hospeda a API. Testes: requisitos e casos de teste |
| Link do repositório | https://github.com/lucksza/lucksza-GS---IA-ML |
| Indicador de impacto | Percentual de ruas com situação conhecida em 15 minutos, comparando o simulado sem e com o app |
| ODS conectados | ODS 11 (meta 11.5) e ODS 13 (meta 13.1) |

## Equipe

| Nome | RM |
|---|---|
| Lucca Borges | 554608 |
| Ruan Melo | 557599 |
| Rodrigo Jimenez | 558148 |
| João Victor Franco | 556790 |
| Bruno Leão | 555563 |

## Inteligência Artificial & Machine Learning

**Vídeo da entrega:** https://youtu.be/tuQqgviOnP4

A entrega está na pasta [`ml/`](ml/). Comece pelo [`ml/README.md`](ml/README.md), que explica o conteúdo e como reproduzir. O [notebook executado](ml/elo_nivel_atencao.ipynb), o [relatório](ml/RELATORIO_ML.md) e a [descrição dos dados](ml/dados/README.md) estão na mesma pasta.
