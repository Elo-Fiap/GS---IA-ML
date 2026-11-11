"""Extrai dados horários observados de duas estações automáticas do INMET.

Baixa os pacotes anuais públicos do INMET e usa somente os CSVs das estações:

  A701  SÃO PAULO - MIRANTE
  A771  SÃO PAULO - INTERLAGOS

Saída: ml/dados/brutos/inmet_horario_sp_2023_2025.csv

Detalhes do formato de origem: latin-1, separador ';', decimal ',', 8 linhas de
cabeçalho e -9999 para faltante. O horário vem em UTC. Como o Brasil não adota
horário de verão desde 2019, o horário local é sempre UTC-3 no período.

O pacote de 2026 também é lido porque as 3 últimas horas locais de 31/12/2025
caem em 01/01/2026 no horário UTC.

Os ZIPs ficam na pasta temporária (variável ELO_ML_TMP), fora do projeto. Se o
arquivo final já existir, o script não faz nada (use --refazer para refazer).

Uso: python coletar_inmet.py [--refazer]
"""
from __future__ import annotations

import io
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from comum import DATA_FIM, DATA_INICIO, DIR_BRUTOS, baixar_arquivo, dir_temporario, preparar_console

URL_ZIP = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
ANOS = [2023, 2024, 2025, 2026]
ESTACOES = {"A701": "SAO PAULO - MIRANTE", "A771": "SAO PAULO - INTERLAGOS"}
ARQ_SAIDA = DIR_BRUTOS / "inmet_horario_sp_2023_2025.csv"
LINHAS_CABECALHO = 8

# Trecho que identifica cada coluna de origem (sem acentos e em maiúsculas).
COLUNAS_ORIGEM = {
    "chuva_mm": "PRECIPITACAO TOTAL, HORARIO",
    "pressao_hpa": "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO",
    "temp_c": "TEMPERATURA DO AR - BULBO SECO",
    "umidade_pct": "UMIDADE RELATIVA DO AR, HORARIA",
    "vento_ms": "VENTO, VELOCIDADE HORARIA",
}
COLUNAS_SAIDA = [
    "estacao", "ts_utc", "ts_local", "chuva_mm", "temp_c",
    "umidade_pct", "pressao_hpa", "vento_ms",
]


def normalizar(texto: str) -> str:
    """Remove acentos e padroniza maiúsculas, para achar a coluna pelo nome."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.upper().split())


def garantir_zip(ano: int) -> Path:
    """Baixa o ZIP do ano, se ainda não estiver em cache, e valida o arquivo."""
    destino = dir_temporario("inmet_zips") / f"inmet_{ano}.zip"
    if destino.exists() and zipfile.is_zipfile(destino):
        print(f"INMET {ano}: usando ZIP em cache", flush=True)
        return destino
    print(f"INMET {ano}: baixando ZIP", flush=True)
    baixar_arquivo(URL_ZIP.format(ano=ano), destino)
    if not zipfile.is_zipfile(destino):
        raise RuntimeError(f"Arquivo baixado não é um ZIP válido: {destino}")
    return destino


def ler_estacao(pacote: zipfile.ZipFile, nome: str, estacao: str) -> pd.DataFrame:
    """Lê o CSV de uma estação e devolve as colunas padronizadas."""
    with pacote.open(nome) as bruto:
        texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
        tabela = pd.read_csv(
            texto, sep=";", skiprows=LINHAS_CABECALHO, decimal=",", dtype=str,
            keep_default_na=False, engine="python",
        )

    nomes = {normalizar(coluna): coluna for coluna in tabela.columns}
    achar = lambda trecho: next(orig for norm, orig in nomes.items() if trecho in norm)

    coluna_data = achar("DATA")
    coluna_hora = achar("HORA UTC")

    # O INMET muda o formato entre anos: "2023/01/01" e "2019-01-01"; "0000 UTC" e "00:00".
    datas = tabela[coluna_data].str.replace("-", "/", regex=False)
    horas = tabela[coluna_hora].str.replace(" UTC", "", regex=False).str.replace(":", "", regex=False).str.zfill(4)
    ts_utc = pd.to_datetime(datas + " " + horas, format="%Y/%m/%d %H%M")

    saida = pd.DataFrame({"estacao": estacao, "ts_utc": ts_utc})
    for destino, trecho in COLUNAS_ORIGEM.items():
        coluna = achar(trecho)
        valores = tabela[coluna].str.strip().str.replace(",", ".", regex=False)
        numeros = pd.to_numeric(valores.replace({"": None}), errors="coerce")
        saida[destino] = numeros.where(numeros > -9000)  # -9999 indica faltante
    return saida


def main() -> int:
    preparar_console()
    argumentos = sys.argv[1:]
    if ARQ_SAIDA.exists() and "--refazer" not in argumentos:
        print(f"INMET: {ARQ_SAIDA.name} já existe; nada a fazer", flush=True)
        return 0
    DIR_BRUTOS.mkdir(parents=True, exist_ok=True)

    partes = []
    for ano in ANOS:
        with zipfile.ZipFile(garantir_zip(ano)) as pacote:
            for estacao in ESTACOES:
                padrao = re.compile(rf"_{estacao}_.*\.csv$", re.IGNORECASE)
                achados = [nome for nome in pacote.namelist() if padrao.search(nome)]
                if len(achados) != 1:
                    print(f"ATENÇÃO: {ano}/{estacao}: {len(achados)} arquivos encontrados: {achados}", flush=True)
                    if not achados:
                        continue
                partes.append(ler_estacao(pacote, achados[0], estacao))
                print(f"  {ano}/{estacao}: {achados[0].split('/')[-1]} ({len(partes[-1])} linhas)", flush=True)

    dados = pd.concat(partes, ignore_index=True)
    dados["ts_local"] = dados["ts_utc"] - pd.Timedelta(hours=3)  # UTC-3 fixo no período
    inicio = pd.Timestamp(DATA_INICIO)
    fim = pd.Timestamp(DATA_FIM) + pd.Timedelta(hours=23)
    dados = dados[(dados["ts_local"] >= inicio) & (dados["ts_local"] <= fim)]

    duplicadas = int(dados.duplicated(["estacao", "ts_utc"]).sum())
    if duplicadas:
        print(f"ATENÇÃO: {duplicadas} linhas duplicadas por estação e horário removidas", flush=True)
        dados = dados.drop_duplicates(["estacao", "ts_utc"], keep="first")

    dados = dados.sort_values(["estacao", "ts_utc"])
    for coluna in ("ts_utc", "ts_local"):
        dados[coluna] = dados[coluna].dt.strftime("%Y-%m-%d %H:%M")

    temporario = ARQ_SAIDA.with_name(ARQ_SAIDA.name + ".tmp")
    dados[COLUNAS_SAIDA].to_csv(temporario, index=False, encoding="utf-8")
    os.replace(temporario, ARQ_SAIDA)
    print(f"INMET concluído: {len(dados)} linhas em {ARQ_SAIDA.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
