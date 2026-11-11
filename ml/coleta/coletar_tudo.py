"""Executa toda a coleta na ordem certa e confere o resultado no final.

Ordem:
  1. coletar_cge.py              registros de alagamento do CGE
  2. coletar_subprefeituras.py   limites do GeoSampa e mapa de nomes (usa o CGE)
  3. coletar_inmet.py            estações do INMET
  4. coletar_openmeteo.py        chuva por subprefeitura e previsão D-1 (usa o GeoSampa)
  5. conferir_coleta.py          relatório de conferência dos arquivos

Cada etapa pode ser repetida sem refazer o que já foi baixado. A primeira etapa
que falhar interrompe a execução. Para baixar de novo uma fonte, apague o arquivo
dela em dados/brutos/ antes de rodar. No CGE, apague também cge_datas_coletadas.csv.

Uso: python coletar_tudo.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ETAPAS = [
    "coletar_cge.py",
    "coletar_subprefeituras.py",
    "coletar_inmet.py",
    "coletar_openmeteo.py",
    "conferir_coleta.py",
]


def main() -> int:
    for etapa in ETAPAS:
        print(f"\n=== {etapa} ===", flush=True)
        resultado = subprocess.run([sys.executable, str(PASTA / etapa)])
        if resultado.returncode != 0:
            print(f"Etapa interrompida: {etapa} (código {resultado.returncode})", flush=True)
            return resultado.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
