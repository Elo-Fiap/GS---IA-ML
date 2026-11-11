"""Utilitários compartilhados pelos scripts de coleta de dados (projeto Elo, ML).

Usa apenas a biblioteca padrão do Python. Os outros scripts importam daqui os
caminhos do projeto, o período de estudo e as funções de download com novas
tentativas (retry com backoff).
"""
from __future__ import annotations

import http.client
import os
import random
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

# Pastas do projeto: os scripts ficam em ml/coleta e os dados em ml/dados/brutos.
RAIZ_ML = Path(__file__).resolve().parents[1]
DIR_BRUTOS = RAIZ_ML / "dados" / "brutos"

# Período de estudo definido no escopo do grupo.
DATA_INICIO = date(2023, 1, 1)
DATA_FIM = date(2025, 12, 31)

# User-Agent genérico: identifica uso acadêmico, sem dado pessoal.
USER_AGENT = "Mozilla/5.0 (compatible; coleta-academica-citizentech/1.0)"


class FalhaDeColeta(RuntimeError):
    """Download que falhou mesmo depois de todas as tentativas."""


def preparar_console() -> None:
    """Evita erro de codificação ao imprimir acentos no console do Windows."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", line_buffering=True)


def datas_do_periodo() -> Iterator[date]:
    """Percorre todos os dias do período de estudo, em ordem."""
    dia = DATA_INICIO
    while dia <= DATA_FIM:
        yield dia
        dia += timedelta(days=1)


def dir_temporario(subpasta: str = "") -> Path:
    """Pasta para arquivos temporários, fora do projeto.

    Use a variável de ambiente ELO_ML_TMP para escolher o local. Sem ela, usa a
    pasta temporária do sistema. Os ZIPs do INMET (cerca de 100 MB cada) e os
    checkpoints ficam aqui, para não irem parar no repositório.
    """
    base = os.environ.get("ELO_ML_TMP")
    pasta = Path(base) if base else Path(tempfile.gettempdir()) / "elo_ml_coleta"
    if subpasta:
        pasta = pasta / subpasta
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _requisicao(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    )


def _espera_erro(erro: Exception, tentativa: int, espera_inicial: float, espera_429: float) -> float:
    """Calcula quanto esperar antes da próxima tentativa."""
    if isinstance(erro, urllib.error.HTTPError) and erro.code == 429:
        # Limite de taxa: respeita o Retry-After quando o servidor informa.
        pedido = erro.headers.get("Retry-After") if erro.headers else None
        if pedido and pedido.isdigit():
            return max(float(pedido), espera_429)
        return espera_429
    # Backoff exponencial com um pouco de aleatoriedade.
    return espera_inicial * (2 ** (tentativa - 1)) + random.uniform(0, 1)


def _erro_e_definitivo(erro: Exception) -> bool:
    """Erros 4xx (exceto 429 e 408) não melhoram com nova tentativa."""
    return (
        isinstance(erro, urllib.error.HTTPError)
        and 400 <= erro.code < 500
        and erro.code not in (408, 429)
    )


ERROS_DE_REDE = (
    urllib.error.URLError,  # inclui HTTPError
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
    OSError,
)


def baixar(
    url: str,
    tentativas: int = 6,
    espera_inicial: float = 2.0,
    espera_429: float = 65.0,
    timeout: float = 120.0,
) -> bytes:
    """Baixa uma URL inteira para a memória, repetindo em caso de falha."""
    ultimo_erro: Exception | None = None
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(_requisicao(url), timeout=timeout) as resposta:
                corpo = resposta.read()
                esperado = resposta.headers.get("Content-Length")
                if esperado is not None and int(esperado) != len(corpo):
                    raise ConnectionError(
                        f"download truncado: {len(corpo)} de {esperado} bytes"
                    )
                return corpo
        except ERROS_DE_REDE as erro:
            ultimo_erro = erro
            if _erro_e_definitivo(erro):
                break
            if n < tentativas:
                espera = _espera_erro(erro, n, espera_inicial, espera_429)
                print(f"  tentativa {n} falhou ({erro!r}); aguardando {espera:.0f} s", flush=True)
                time.sleep(espera)
    raise FalhaDeColeta(f"{url} -> {ultimo_erro!r}")


def baixar_arquivo(url: str, destino: Path, tentativas: int = 5, timeout: float = 180.0) -> None:
    """Baixa um arquivo grande em partes para o disco, com novas tentativas."""
    parcial = destino.with_name(destino.name + ".parcial")
    ultimo_erro: Exception | None = None
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(_requisicao(url), timeout=timeout) as resposta:
                esperado = resposta.headers.get("Content-Length")
                recebidos = 0
                with open(parcial, "wb") as saida:
                    while True:
                        bloco = resposta.read(1024 * 1024)
                        if not bloco:
                            break
                        saida.write(bloco)
                        recebidos += len(bloco)
            if esperado is not None and int(esperado) != recebidos:
                raise ConnectionError(f"download truncado: {recebidos} de {esperado} bytes")
            os.replace(parcial, destino)
            return
        except ERROS_DE_REDE as erro:
            ultimo_erro = erro
            if _erro_e_definitivo(erro):
                break
            if n < tentativas:
                espera = _espera_erro(erro, n, 5.0, 65.0)
                print(f"  tentativa {n} falhou ({erro!r}); aguardando {espera:.0f} s", flush=True)
                time.sleep(espera)
    raise FalhaDeColeta(f"{url} -> {ultimo_erro!r}")
