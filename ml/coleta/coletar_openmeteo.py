"""Baixa da Open-Meteo a chuva por subprefeitura e a previsão emitida na véspera.

Consulta o centroide de cada subprefeitura e gera em ml/dados/brutos:

  openmeteo_horario_subprefeituras_2023_2025.csv.gz
      Archive API: chuva (mm) e umidade do solo de 0 a 7 cm, de hora em hora,
      de 2023 a 2025. É reanálise (modelo meteorológico + observações), e não
      medição direta na subprefeitura.

  openmeteo_previsao_d1_jma_horario_2023_2025.csv.gz
      Previous Runs API: chuva prevista 24 horas antes pelo modelo JMA GSM, de
      hora em hora, de 2023 a 2025. É a informação que existe de verdade na hora
      de decidir. O JMA é o único modelo da API com previsão desde 2023, então a
      mesma fonte serve para o treino e para o teste.

Depende de ml/dados/brutos/subprefeituras_geosampa.csv (coletar_subprefeituras.py).

Limite de uso: a API gratuita conta a chamada por dia consultado (cerca de uma
chamada a cada 14 dias de dados), até 600 por minuto. As pausas abaixo mantêm o
script bem abaixo disso, e erros 429 são tratados com espera e nova tentativa.

Cada subprefeitura baixada vira um arquivo parcial na pasta temporária
(ELO_ML_TMP). Ao executar de novo, só o que falta é baixado.

Uso: python coletar_openmeteo.py [--refazer]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from comum import DATA_FIM, DATA_INICIO, DIR_BRUTOS, FalhaDeColeta, baixar, dir_temporario, preparar_console

URL_ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
URL_PREVISAO = "https://previous-runs-api.open-meteo.com/v1/forecast"
FUSO = "America/Sao_Paulo"

ARQ_SUBPREFEITURAS = DIR_BRUTOS / "subprefeituras_geosampa.csv"
ARQ_ARQUIVO = DIR_BRUTOS / "openmeteo_horario_subprefeituras_2023_2025.csv.gz"
ARQ_PREVISAO = DIR_BRUTOS / "openmeteo_previsao_d1_jma_horario_2023_2025.csv.gz"

PAUSA_ARQUIVO = 10.0  # segundos; cada chamada de 3 anos pesa cerca de 78 chamadas
PAUSA_PREVISAO = 10.0  # segundos; cada chamada de 3 anos pesa cerca de 78 chamadas
MODELO_PREVISAO = "jma_gsm"
HORAS_ARQUIVO = ((DATA_FIM - DATA_INICIO + timedelta(days=1)).days) * 24

COMPRESSAO = {"method": "gzip", "compresslevel": 9, "mtime": 1}


def fatia_nome(subprefeitura: str) -> str:
    """Transforma o nome em algo seguro para nome de arquivo."""
    return re.sub(r"[^A-Z0-9]+", "_", subprefeitura)


def consultar(url_base: str, parametros: dict[str, object]) -> dict:
    """Faz uma chamada à API e devolve o JSON já validado."""
    url = f"{url_base}?{urlencode(parametros, safe=',')}"
    resposta = json.loads(baixar(url, tentativas=8, espera_inicial=5.0, espera_429=65.0).decode("utf-8"))
    if resposta.get("error"):
        raise FalhaDeColeta(f"{url} -> {resposta.get('reason')}")
    return resposta


def baixar_arquivo_historico(sub: pd.Series, destino: Path) -> None:
    resposta = consultar(URL_ARQUIVO, {
        "latitude": f"{sub.lat_centroide:.6f}",
        "longitude": f"{sub.lon_centroide:.6f}",
        "start_date": DATA_INICIO.isoformat(),
        "end_date": DATA_FIM.isoformat(),
        "hourly": "precipitation,soil_moisture_0_to_7cm",
        "timezone": FUSO,
    })
    horario = resposta["hourly"]
    if len(horario["time"]) != HORAS_ARQUIVO:
        raise FalhaDeColeta(f"{sub.subprefeitura}: {len(horario['time'])} horas, esperado {HORAS_ARQUIVO}")
    parte = pd.DataFrame({
        "ts_local": horario["time"],
        "subprefeitura": sub.subprefeitura,
        "chuva_mm": horario["precipitation"],
        "umidade_solo_0_7cm": horario["soil_moisture_0_to_7cm"],
        "grid_lat": resposta["latitude"],
        "grid_lon": resposta["longitude"],
    })
    gravar_parte(parte, destino)


def baixar_previsao_d1(sub: pd.Series, destino: Path) -> None:
    resposta = consultar(URL_PREVISAO, {
        "latitude": f"{sub.lat_centroide:.6f}",
        "longitude": f"{sub.lon_centroide:.6f}",
        "start_date": DATA_INICIO.isoformat(),
        "end_date": DATA_FIM.isoformat(),
        "hourly": "precipitation_previous_day1",
        "models": MODELO_PREVISAO,
        "timezone": FUSO,
    })
    horario = resposta["hourly"]
    if len(horario["time"]) != HORAS_ARQUIVO:
        raise FalhaDeColeta(f"{sub.subprefeitura}: {len(horario['time'])} horas, esperado {HORAS_ARQUIVO}")
    parte = pd.DataFrame({
        "ts_local": horario["time"],
        "subprefeitura": sub.subprefeitura,
        "chuva_prevista_d1_mm": horario["precipitation_previous_day1"],
        "grid_lat": resposta["latitude"],
        "grid_lon": resposta["longitude"],
    })
    gravar_parte(parte, destino)


def gravar_parte(parte: pd.DataFrame, destino: Path) -> None:
    """Grava o arquivo parcial de uma subprefeitura de forma atômica."""
    parte["ts_local"] = pd.to_datetime(parte["ts_local"]).dt.strftime("%Y-%m-%d %H:%M")
    temporario = destino.with_name(destino.name + ".tmp")
    parte.to_csv(temporario, index=False, encoding="utf-8")
    os.replace(temporario, destino)


def executar_lote(rotulo, subs, pasta, funcao, pausa) -> list[str]:
    """Baixa o que falta de um conjunto e devolve a lista de falhas."""
    falhas: list[str] = []
    for indice, sub in enumerate(subs.itertuples(index=False), start=1):
        destino = pasta / f"{fatia_nome(sub.subprefeitura)}.csv"
        if destino.exists():
            continue
        print(f"{rotulo}: {indice}/{len(subs)} {sub.subprefeitura}", flush=True)
        try:
            funcao(sub, destino)
        except FalhaDeColeta as erro:
            falhas.append(f"{sub.subprefeitura}: {erro}")
            print(f"FALHA {rotulo} {sub.subprefeitura}: {erro}", flush=True)
        time.sleep(pausa)
    return falhas


def consolidar(subs: pd.DataFrame, pasta: Path, saida: Path, chave: list[str]) -> None:
    """Junta os arquivos parciais em um único CSV compactado."""
    partes = [pd.read_csv(pasta / f"{fatia_nome(nome)}.csv") for nome in subs["subprefeitura"]]
    dados = pd.concat(partes, ignore_index=True)
    dados = dados.sort_values(chave).reset_index(drop=True)
    temporario = saida.with_name(saida.name + ".tmp")
    dados.to_csv(temporario, index=False, encoding="utf-8", compression=COMPRESSAO)
    os.replace(temporario, saida)
    print(f"{saida.name}: {len(dados)} linhas", flush=True)


def main() -> int:
    preparar_console()
    refazer = "--refazer" in sys.argv[1:]
    subs = pd.read_csv(ARQ_SUBPREFEITURAS).sort_values("subprefeitura")

    pasta_arquivo = dir_temporario("openmeteo_arquivo")
    pasta_previsao = dir_temporario("openmeteo_previsao_d1_jma")
    if refazer:
        for pasta in (pasta_arquivo, pasta_previsao):
            for parcial in pasta.glob("*.csv"):
                parcial.unlink()

    falhas: list[str] = []
    if refazer or not ARQ_ARQUIVO.exists():
        falhas += executar_lote("Archive", subs, pasta_arquivo, baixar_arquivo_historico, PAUSA_ARQUIVO)
        if not falhas:
            consolidar(subs, pasta_arquivo, ARQ_ARQUIVO, ["subprefeitura", "ts_local"])
    else:
        print(f"{ARQ_ARQUIVO.name} já existe; nada a fazer", flush=True)

    if refazer or not ARQ_PREVISAO.exists():
        falhas_previsao = executar_lote("Previsão D-1", subs, pasta_previsao, baixar_previsao_d1, PAUSA_PREVISAO)
        if not falhas_previsao:
            consolidar(subs, pasta_previsao, ARQ_PREVISAO, ["subprefeitura", "ts_local"])
        falhas += falhas_previsao
    else:
        print(f"{ARQ_PREVISAO.name} já existe; nada a fazer", flush=True)

    if falhas:
        print("Downloads incompletos. Execute de novo para continuar de onde parou:", flush=True)
        for falha in falhas:
            print("  " + falha, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
