"""Confere os arquivos coletados e compara com os números citados no escopo do grupo.

O relatório sai no console e também em ml/dados/conferencia_coleta.txt.
Este script só lê os dados: nada é corrigido ou removido aqui.

Uso: python conferir_coleta.py
"""
from __future__ import annotations

import sys
from datetime import datetime

import pandas as pd

from comum import DATA_FIM, DATA_INICIO, DIR_BRUTOS, RAIZ_ML, datas_do_periodo, preparar_console

ARQ_REGISTROS = DIR_BRUTOS / "cge_alagamentos_2023_2025.csv"
ARQ_DATAS = DIR_BRUTOS / "cge_datas_coletadas.csv"
ARQ_DIVERGENCIAS = DIR_BRUTOS / "cge_divergencias.csv"
ARQ_INMET = DIR_BRUTOS / "inmet_horario_sp_2023_2025.csv"
ARQ_SUBS = DIR_BRUTOS / "subprefeituras_geosampa.csv"
ARQ_MAPA = DIR_BRUTOS / "mapa_nomes_cge_geosampa.csv"
ARQ_ARQUIVO = DIR_BRUTOS / "openmeteo_horario_subprefeituras_2023_2025.csv.gz"
ARQ_PREVISAO = DIR_BRUTOS / "openmeteo_previsao_d1_jma_horario_2023_2025.csv.gz"
ARQ_RELATORIO = RAIZ_ML / "dados" / "conferencia_coleta.txt"

TODOS = [ARQ_REGISTROS, ARQ_DATAS, ARQ_INMET, ARQ_SUBS, ARQ_MAPA, ARQ_ARQUIVO, ARQ_PREVISAO]

# Números declarados no escopo do grupo, usados só para comparação.
ESCOPO = {
    "pontos": 2137,
    "dias": 1055,
    "dias_ano_min": 68,
    "dias_ano_max": 82,
    "se": 335,
    "cidade_tiradentes": 5,
    "pct_avenidas": 53.0,
}

_linhas: list[str] = []


def diga(texto: object = "") -> None:
    print(texto, flush=True)
    _linhas.append(str(texto))


def titulo(texto: str) -> None:
    diga("")
    diga(f"=== {texto}")


def faltantes(dados: pd.DataFrame) -> str:
    serie = dados.isna().mean().mul(100).round(3)
    return ", ".join(f"{c}={v}%" for c, v in serie.items())


def hora_valida(valor: object) -> bool:
    if not isinstance(valor, str):
        return False
    partes = valor.split(":")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        return False
    return 0 <= int(partes[0]) <= 23 and 0 <= int(partes[1]) <= 59


def main() -> int:
    preparar_console()
    diga(f"Conferência gerada em {datetime.now().astimezone().isoformat(timespec='seconds')}")
    diga(f"Período esperado: {DATA_INICIO} a {DATA_FIM}")

    titulo("Arquivos")
    tabelas: dict = {}
    for caminho in TODOS:
        if not caminho.exists():
            diga(f"AUSENTE: {caminho.name}")
            continue
        tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False, na_values=[""])
        tabelas[caminho] = tabela
        diga(f"{caminho.name}: {len(tabela)} linhas, {caminho.stat().st_size / 1e6:.2f} MB")
    if ARQ_DIVERGENCIAS.exists():
        diga(f"{ARQ_DIVERGENCIAS.name}: {sum(1 for _ in open(ARQ_DIVERGENCIAS, encoding='utf-8')) - 1} linhas")
    else:
        diga(f"{ARQ_DIVERGENCIAS.name}: não existe (nenhuma divergência registrada)")

    if ARQ_REGISTROS not in tabelas or ARQ_DATAS not in tabelas:
        diga("CGE incompleto: conferência interrompida")
        return 1

    registros = tabelas[ARQ_REGISTROS].copy()
    datas = tabelas[ARQ_DATAS].copy()

    titulo("CGE: cobertura de datas")
    esperadas = {d.isoformat() for d in datas_do_periodo()}
    presentes = set(datas["data"])
    diga(f"Datas no período: {len(esperadas)}; coletadas: {len(presentes)}; duplicadas: {int(datas['data'].duplicated().sum())}")
    diga(f"Faltando: {sorted(esperadas - presentes)[:20]}")
    diga(f"Fora do período: {sorted(presentes - esperadas)[:20]}")
    diga(datas["situacao"].value_counts().to_string())

    titulo("CGE: validações internas por dia")
    for coluna in ("n_registros", "resumo_transitaveis", "resumo_intransitaveis"):
        datas[coluna] = datas[coluna].astype(int)
    diverge = datas[datas["n_registros"] != datas["resumo_transitaveis"] + datas["resumo_intransitaveis"]]
    diga(f"Dias em que n_registros != resumo lateral: {len(diverge)}")
    por_dia = registros.groupby("data").size()
    conferido = datas.set_index("data")["n_registros"]
    diferenca = conferido.sub(por_dia.reindex(conferido.index).fillna(0).astype(int))
    diga(f"Dias em que o CSV de registros difere de n_registros: {int((diferenca != 0).sum())}")
    if len(diverge):
        diga(diverge.head(20).to_string(index=False))

    registros["ano"] = registros["data"].str[:4]
    datas["ano"] = datas["data"].str[:4]

    titulo("CGE: registros e dias por ano")
    resumo = pd.DataFrame({
        "registros": registros.groupby("ano").size(),
        "dias_com_registro": datas[datas["situacao"] == "com_registro"].groupby("ano").size(),
        "dias_coletados": datas.groupby("ano").size(),
    })
    diga(resumo.to_string())
    diga(f"Total de registros: {len(registros)}")
    diga(f"Total de dias com registro: {int((datas['situacao'] == 'com_registro').sum())}")

    titulo("CGE: status")
    diga(registros["status_css"].value_counts(dropna=False).to_string())
    diga(registros["transitavel"].value_counts(dropna=False).to_string())
    diga(registros["zona"].value_counts(dropna=False).to_string())

    titulo("CGE: qualidade dos registros")
    inicio_ok = registros["hora_inicio"].map(hora_valida)
    fim_ok = registros["hora_fim"].map(hora_valida)
    diga(f"hora_inicio inválida ou vazia: {int((~inicio_ok).sum())}")
    diga(f"hora_fim inválida ou vazia: {int((~fim_ok).sum())}")
    ambos = inicio_ok & fim_ok
    invertidos = registros[ambos & (registros["hora_fim"] < registros["hora_inicio"])]
    diga(f"hora_fim anterior a hora_inicio (pode virar o dia): {len(invertidos)}")
    if len(invertidos):
        diga(invertidos[["data", "subprefeitura_cge", "hora_inicio", "hora_fim", "local"]].head(10).to_string(index=False))
    colunas_originais = [c for c in registros.columns if c != "ano"]
    duplicados = registros[registros.duplicated(colunas_originais, keep="first")]
    diga(f"Duplicados exatos: {len(duplicados)}")
    if len(duplicados):
        diga(duplicados[["data", "subprefeitura_cge", "hora_inicio", "local"]].head(10).to_string(index=False))
    diga(f"Faltantes em registros: {faltantes(registros[colunas_originais])}")
    diga(f"Faltantes em datas: {faltantes(datas.drop(columns='ano'))}")

    titulo("CGE: tipo de via (primeira palavra do local)")
    primeira = registros["local"].fillna("").str.upper().str.extract(r"^([A-Z\.]+)", expand=False)
    diga(primeira.value_counts(dropna=False).head(15).to_string())
    avenidas = registros["local"].fillna("").str.upper().str.contains(r"^(?:AV\b|AV\.|AVENIDA\b)", regex=True)
    pct_avenidas = float(avenidas.mean() * 100)
    diga(f"Registros em avenidas (local começa com AV/AVENIDA): {int(avenidas.sum())} ({pct_avenidas:.1f}%)")
    marginais = registros["local"].fillna("").str.upper().str.startswith("MARGINAL")
    diga(f"Registros em marginais (local começa com MARGINAL): {int(marginais.sum())} ({marginais.mean() * 100:.1f}%)")

    titulo("CGE: subprefeituras")
    if ARQ_MAPA in tabelas and ARQ_SUBS in tabelas:
        mapa = tabelas[ARQ_MAPA].set_index("subprefeitura_cge")["subprefeitura"]
        registros["subprefeitura"] = registros["subprefeitura_cge"].map(mapa)
        diga(f"Registros sem subprefeitura mapeada: {int(registros['subprefeitura'].isna().sum())}")
        oficiais = tabelas[ARQ_SUBS]["subprefeitura"]
        contagem = registros["subprefeitura"].value_counts().reindex(oficiais).fillna(0).astype(int).sort_values(ascending=False)
        diga("Top 5:")
        diga(contagem.head(5).to_string())
        diga("Bottom 5:")
        diga(contagem.tail(5).to_string())
        diga(f"Subprefeituras sem nenhum registro: {list(contagem[contagem == 0].index)}")
        total_se = int(contagem.get("SE", 0))
        total_ct = int(contagem.get("CIDADE TIRADENTES", 0))
    else:
        diga("Mapa de nomes ainda não gerado; usando os nomes do CGE")
        contagem = registros["subprefeitura_cge"].value_counts()
        diga(contagem.head(5).to_string())
        diga(contagem.tail(5).to_string())
        total_se = int(contagem.get("Sé", 0))
        total_ct = int(contagem.get("Cidade Tiradentes", 0))

    titulo("Comparação com o escopo do grupo")
    dias_ano = datas[datas["situacao"] == "com_registro"].groupby("ano").size()
    diga(f"Pontos: escopo {ESCOPO['pontos']} | coletado {len(registros)} | diferença {len(registros) - ESCOPO['pontos']}")
    diga(f"Dias: escopo {ESCOPO['dias']} | no período {len(esperadas)} | coletados {len(presentes)} | sem_registro confirmados {int((datas['situacao'] == 'sem_registro').sum())}")
    diga(f"Dias com alagamento por ano: escopo {ESCOPO['dias_ano_min']} a {ESCOPO['dias_ano_max']} | coletado {dias_ano.to_dict()}")
    diga(f"Sé: escopo {ESCOPO['se']} | coletado {total_se}")
    diga(f"Cidade Tiradentes: escopo {ESCOPO['cidade_tiradentes']} | coletado {total_ct}")
    diga(f"% em avenidas: escopo {ESCOPO['pct_avenidas']} | coletado {pct_avenidas:.1f}")

    if ARQ_INMET in tabelas:
        titulo("INMET")
        inmet = tabelas[ARQ_INMET].copy()
        inmet["ano"] = inmet["ts_local"].str[:4]
        diga(f"Intervalo local: {inmet['ts_local'].min()} a {inmet['ts_local'].max()}")
        diga(f"Linhas por estação: {inmet.groupby('estacao').size().to_dict()}")
        tabela = inmet.assign(falta=inmet["chuva_mm"].isna()).groupby(["estacao", "ano"])["falta"].agg(["mean", "size"])
        tabela["mean"] = (tabela["mean"] * 100).round(2)
        diga("% de faltantes de chuva por estação e ano:")
        diga(tabela.rename(columns={"mean": "pct_faltante", "size": "horas"}).to_string())
        diga(f"Faltantes: {faltantes(inmet.drop(columns='ano'))}")
        chuva = pd.to_numeric(inmet["chuva_mm"], errors="coerce")
        diga(f"Chuva horária: mín {chuva.min()}, máx {chuva.max()}, soma por estação {inmet.assign(c=chuva).groupby('estacao')['c'].sum().round(1).to_dict()}")

    if ARQ_SUBS in tabelas:
        titulo("Subprefeituras")
        subs = tabelas[ARQ_SUBS]
        diga(f"Linhas: {len(subs)}; faltantes: {faltantes(subs)}")
        area = pd.to_numeric(subs["area_km2"]).sum()
        diga(f"Soma das áreas: {area:.1f} km²")
        lat = pd.to_numeric(subs["lat_centroide"])
        lon = pd.to_numeric(subs["lon_centroide"])
        diga(f"Latitude: {lat.min()} a {lat.max()}; longitude: {lon.min()} a {lon.max()}")
        diga(f"Elevação (m): {pd.to_numeric(subs['elevacao_m']).min()} a {pd.to_numeric(subs['elevacao_m']).max()}")

    if ARQ_ARQUIVO in tabelas:
        titulo("Open-Meteo: histórico (reanálise)")
        arquivo = tabelas[ARQ_ARQUIVO]
        grade = arquivo[["grid_lat", "grid_lon"]].drop_duplicates()
        diga(f"Pontos de grade distintos: {len(grade)}")
        diga(f"Subprefeituras por ponto de grade: {arquivo.drop_duplicates('subprefeitura').groupby(['grid_lat', 'grid_lon']).size().to_dict()}")
        diga(f"Intervalo: {arquivo['ts_local'].min()} a {arquivo['ts_local'].max()}")
        diga(f"Linhas por subprefeitura: {arquivo.groupby('subprefeitura').size().unique().tolist()}")
        diga(f"Faltantes: {faltantes(arquivo)}")

    if ARQ_PREVISAO in tabelas:
        titulo("Open-Meteo: previsão D-1")
        previsao = tabelas[ARQ_PREVISAO]
        diga(f"Intervalo: {previsao['ts_local'].min()} a {previsao['ts_local'].max()}")
        diga(f"Linhas por subprefeitura: {previsao.groupby('subprefeitura').size().unique().tolist()}")
        cobertura = float(previsao["chuva_prevista_d1_mm"].notna().mean() * 100)
        diga(f"Cobertura (% não nulo): {cobertura:.2f}%")
        previsao = previsao.assign(mes=previsao["ts_local"].str[:7])
        por_mes = previsao["chuva_prevista_d1_mm"].notna().groupby(previsao["mes"]).mean().mul(100).round(1)
        diga(f"Cobertura por mês: {por_mes.to_dict()}")

    ARQ_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_RELATORIO.write_text("\n".join(_linhas) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
