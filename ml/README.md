# Elo · Inteligência Artificial & Machine Learning

Parte de Machine Learning da CitizenTech **Elo** (Global Solution 2026.2, FIAP, Engenharia de Software). A Ficha da CitizenTech está no [README principal do repositório](../README.md).

**Vídeo da entrega:** https://youtu.be/tuQqgviOnP4

**Como a parte de ML contribui para os ODS.** A meta 11.5 trata de reduzir as mortes e as perdas causadas por desastres, e a meta 13.1, de fortalecer a resiliência a riscos climáticos. O nível de atenção ajuda quem coordena o bairro a se preparar nos dias de maior risco e a abrir a chamada mais cedo. A contribuição é de preparo: este trabalho não mede vidas salvas.

## O que há nesta pasta

| Item | Conteúdo |
|---|---|
| [`elo_nivel_atencao.ipynb`](elo_nivel_atencao.ipynb) | Notebook executado: problema, dados, preparação, treino, resultados, overfitting e conclusão |
| [`RELATORIO_ML.md`](RELATORIO_ML.md) | Relatório do problema à conclusão (2 páginas) |
| [`dados/README.md`](dados/README.md) | Fonte, link, período e dicionário de cada base |
| `dados/brutos/` | Dados reais usados no notebook |
| `coleta/` | Scripts que baixam os dados das fontes públicas |
| `figuras/` | Gráficos gerados pelo notebook |
| `resultados/` | Tabela da busca de hiperparâmetros e métricas finais em CSV e JSON |
| [`requirements.txt`](requirements.txt) | Bibliotecas e versões |
| [`prompts.md`](prompts.md) | Registro do uso de IA |
| [`ROTEIRO_VIDEO.md`](ROTEIRO_VIDEO.md) | Roteiro do vídeo de até 5 minutos |

## Como reproduzir

Requer Python 3.11. Os dados já estão em `dados/brutos/`, então não é preciso coletar nada.

```bash
cd ml
pip install -r requirements.txt
```

Abra `elo_nivel_atencao.ipynb` e execute todas as células (cerca de 3 minutos). A semente é fixa, e cada modelo usa uma única thread, para que o resultado se repita.

Para coletar de novo das fontes, rode `python coleta/coletar_tudo.py` a partir de `ml/`. Leva cerca de 1 hora, porque a coleta respeita o limite de acesso do CGE.

## Resultado em uma frase

Só com o que existe na manhã do dia, a previsão da véspera e a subprefeitura, a Regressão Logística alcança PR-AUC de 0,176 em 2025, contra 0,029 do acaso e 0,112 usando só a previsão. O nível alto abriria a chamada em 42 de cada 100 alagamentos registrados, e quase não avisa onde o CGE registrou pouco. Por isso, o modelo deve apoiar o coordenador, nunca substituir o aviso oficial.
