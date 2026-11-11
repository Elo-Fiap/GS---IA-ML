"""Coleta o histórico de pontos de alagamento do CGE (Prefeitura de São Paulo).

Consulta a página pública de alagamentos dia a dia e gera dois arquivos em
ml/dados/brutos:

  cge_alagamentos_2023_2025.csv  uma linha por registro de ponto de alagamento
  cge_datas_coletadas.csv        uma linha por data consultada com sucesso

Regras importantes:
- Dia sem alagamento só é aceito quando a página traz o texto oficial
  "Não há registros de alagamentos para essa data.". Falha de rede ou página
  inesperada NUNCA vira "sem_registro": a data fica pendente e é reportada.
- O próprio CSV de datas funciona como checkpoint. Ao executar de novo, só as
  datas que faltam são consultadas.
- Cada dia é validado contra os totais que a própria página publica. Dias que
  divergem ficam listados em cge_divergencias.csv (o arquivo só existe se houver).
- Se o site recusar várias consultas seguidas (por exemplo, HTTP 403), o script
  para na hora. Não tente contornar a recusa: espere e execute de novo mais tarde.

Uso: python coletar_cge.py
"""
from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import date, datetime
from html.parser import HTMLParser

from comum import (
    DIR_BRUTOS,
    FalhaDeColeta,
    baixar,
    datas_do_periodo,
    preparar_console,
)

URL_BASE = "https://www.cgesp.org/v3/alagamentos.jsp"
# O site passou a responder 403 depois de ~520 consultas seguidas com pausa de 0,2 s.
# Por isso a pausa é maior, e o script desiste ao ver recusas seguidas.
PAUSA_ENTRE_DIAS = 2.0  # segundos
TENTATIVAS_PAGINA_INVALIDA = 3
LIMITE_FALHAS_SEGUIDAS = 3  # interrompe em vez de insistir com o servidor

ARQ_REGISTROS = DIR_BRUTOS / "cge_alagamentos_2023_2025.csv"
ARQ_DATAS = DIR_BRUTOS / "cge_datas_coletadas.csv"
ARQ_DIVERGENCIAS = DIR_BRUTOS / "cge_divergencias.csv"

COLUNAS_REGISTROS = [
    "data", "zona", "subprefeitura_cge", "status_css", "transitavel",
    "hora_inicio", "hora_fim", "local", "sentido", "referencia",
]
COLUNAS_DATAS = [
    "data", "situacao", "n_registros",
    "resumo_transitaveis", "resumo_intransitaveis", "coletado_em",
]
COLUNAS_DIVERGENCIAS = [
    "data", "n_registros", "resumo_total", "soma_pts_subprefeituras", "motivo",
]

TEXTO_SEM_REGISTRO = "Não há registros de alagamentos para essa data."


class PaginaInvalida(ValueError):
    """A página respondeu, mas não tem o formato esperado."""


def limpar_texto(texto: str) -> str:
    """Remove quebras e espaços repetidos."""
    return " ".join(texto.split())


class ParserPaginaCGE(HTMLParser):
    """Extrai zona, subprefeitura e pontos de alagamento do HTML da página."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.registros: list[dict[str, str]] = []
        self.pts_declarados: list[int] = []
        self.resumo_transitaveis: list[int] = []
        self.resumo_intransitaveis: list[int] = []
        self.sem_registro = False
        self.data_ecoada: str | None = None
        self._zona = ""
        self._subprefeitura = ""
        self._captura: str | None = None  # campo sendo lido no momento
        self._tag_captura: str | None = None
        self._buffer: list[str] = []
        self._registro: dict[str, str] | None = None
        self._descricoes: list[str] = []

    # ---------------------------------------------------------------- captura
    def _iniciar_captura(self, campo: str, tag: str) -> None:
        self._captura = campo
        self._tag_captura = tag
        self._buffer = []

    def _concluir_captura(self) -> None:
        texto = "".join(self._buffer)
        campo = self._captura
        self._captura = None
        self._tag_captura = None
        if campo == "zona":
            self._zona = limpar_texto(texto)
        elif campo == "subprefeitura":
            self._subprefeitura = limpar_texto(texto)
        elif campo == "pts":
            achado = re.search(r"(\d+)\s*pts", texto)
            if not achado:
                raise PaginaInvalida(f"total de pontos ilegível: {texto!r}")
            self.pts_declarados.append(int(achado.group(1)))
        elif campo == "h1_resumo":
            self._ler_resumo(limpar_texto(texto))
        elif campo == "h2":
            if limpar_texto(texto) == TEXTO_SEM_REGISTRO:
                self.sem_registro = True
        elif campo == "descricao":
            self._descricoes.append(texto)

    def _ler_resumo(self, texto: str) -> None:
        """Lê os títulos 'Transitáveis = N pts' e 'Intransitáveis = N pts'."""
        achado = re.fullmatch(r"(Transitáveis|Intransitáveis)\s*=\s*(\d+)\s*pts", texto)
        if not achado:
            return
        valor = int(achado.group(2))
        if achado.group(1) == "Intransitáveis":
            self.resumo_intransitaveis.append(valor)
        else:
            self.resumo_transitaveis.append(valor)

    # ---------------------------------------------------------------- eventos
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        classes = (atributos.get("class") or "").split()

        if tag == "input" and atributos.get("name") == "dataBusca":
            self.data_ecoada = atributos.get("value")
        elif tag == "h1":
            self._iniciar_captura("zona" if "tit-bairros" in classes else "h1_resumo", "h1")
        elif tag == "h2":
            self._iniciar_captura("h2", "h2")
        elif tag == "td" and "bairro" in classes:
            self._iniciar_captura("subprefeitura", "td")
        elif tag == "td" and "total-pts" in classes:
            self._iniciar_captura("pts", "td")
        elif tag == "div" and "ponto-de-alagamento" in classes:
            self._registro = {"status_css": ""}
            self._descricoes = []
        elif tag == "li" and self._registro is not None:
            if not self._registro["status_css"]:
                estado = [c for c in classes if re.fullmatch(r"(in)?ativo-(in)?transitavel", c)]
                if estado:
                    self._registro["status_css"] = estado[0]
            if "arial-descr-alag" in classes:
                self._iniciar_captura("descricao", "li")
        elif tag == "br" and self._captura:
            self._buffer.append("\n")

    def handle_data(self, data: str) -> None:
        if self._captura:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._captura and tag == self._tag_captura:
            self._concluir_captura()
        if tag == "ul" and self._registro is not None:
            self._fechar_registro()

    # --------------------------------------------------------------- registros
    def _fechar_registro(self) -> None:
        registro = self._registro
        self._registro = None
        if len(self._descricoes) != 2 or not registro["status_css"]:
            raise PaginaInvalida(f"ponto com formato inesperado: {self._descricoes!r}")

        # Primeira descrição: "De 09:34 a 09:36" e, na linha seguinte, o local.
        horario, _, local = self._descricoes[0].strip().partition("\n")
        achado = re.search(r"De\s*(\d{1,2}:\d{2})?\s*a\s*(\d{1,2}:\d{2})?", horario)
        if not achado:
            raise PaginaInvalida(f"horário ilegível: {horario!r}")

        # Segunda descrição: "Sentido: X" e "Referência: Y".
        sentido = re.search(r"Sentido:\s*(.*)", self._descricoes[1])
        referencia = re.search(r"Referência:\s*(.*)", self._descricoes[1], flags=re.S)

        status = registro["status_css"]
        self.registros.append({
            "zona": self._zona,
            "subprefeitura_cge": self._subprefeitura,
            "status_css": status,
            # "intransitavel" contém "transitavel"; por isso testa a negação.
            "transitavel": "0" if "intransitavel" in status else "1",
            "hora_inicio": _normalizar_hora(achado.group(1)),
            "hora_fim": _normalizar_hora(achado.group(2)),
            "local": limpar_texto(local),
            "sentido": limpar_texto(sentido.group(1)) if sentido else "",
            "referencia": limpar_texto(referencia.group(1)) if referencia else "",
        })


def _normalizar_hora(hora: str | None) -> str:
    """Converte '9:34' em '09:34'. Campo ausente vira texto vazio."""
    if not hora:
        return ""
    horas, minutos = hora.split(":")
    return f"{int(horas):02d}:{minutos}"


def ler_pagina(html: str, dia: date) -> ParserPaginaCGE:
    """Interpreta e valida o formato de uma página do CGE."""
    pagina = ParserPaginaCGE()
    pagina.feed(html)
    pagina.close()

    if pagina.data_ecoada != dia.strftime("%d/%m/%Y"):
        raise PaginaInvalida(f"página de outra data: {pagina.data_ecoada!r}")
    if pagina.sem_registro and pagina.registros:
        raise PaginaInvalida("página diz que não há registros, mas traz pontos")
    if not pagina.sem_registro and not pagina.registros:
        raise PaginaInvalida("página sem pontos e sem o texto oficial de dia vazio")
    # O resumo tem quatro títulos: ativos e inativos, para cada tipo.
    if len(pagina.resumo_transitaveis) != 2 or len(pagina.resumo_intransitaveis) != 2:
        raise PaginaInvalida("resumo lateral incompleto")
    return pagina


def coletar_dia(dia: date) -> ParserPaginaCGE:
    """Baixa e interpreta um dia, repetindo se a página vier em formato inválido."""
    url = f"{URL_BASE}?dataBusca={dia:%d/%m/%Y}&enviaBusca=Buscar"
    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS_PAGINA_INVALIDA + 1):
        bruto = baixar(url, timeout=60)
        try:
            return ler_pagina(bruto.decode("utf-8"), dia)
        except (PaginaInvalida, UnicodeDecodeError) as erro:
            ultimo_erro = erro
            time.sleep(2 * tentativa)
    raise FalhaDeColeta(f"{dia}: página inválida após novas tentativas: {ultimo_erro!r}")


def recuperar_checkpoint() -> set[str]:
    """Lê as datas já coletadas e descarta registros de uma execução interrompida.

    Os registros são gravados antes da linha da data. Se o processo parar entre
    os dois passos, sobram registros de uma data ainda pendente: eles são
    removidos aqui para não ficarem duplicados.
    """
    if not ARQ_DATAS.exists():
        if ARQ_REGISTROS.exists():
            ARQ_REGISTROS.unlink()
        return set()

    with open(ARQ_DATAS, newline="", encoding="utf-8") as arquivo:
        feitas = {linha["data"] for linha in csv.DictReader(arquivo)}

    if ARQ_REGISTROS.exists():
        with open(ARQ_REGISTROS, newline="", encoding="utf-8") as arquivo:
            linhas = list(csv.DictReader(arquivo))
        validas = [l for l in linhas if l["data"] in feitas]
        if len(validas) != len(linhas):
            _reescrever(ARQ_REGISTROS, COLUNAS_REGISTROS, validas)
    return feitas


def _reescrever(caminho, colunas: list[str], linhas: list[dict[str, str]]) -> None:
    """Regrava um CSV de forma atômica (arquivo temporário e troca de nome)."""
    temporario = caminho.with_name(caminho.name + ".tmp")
    with open(temporario, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)
    os.replace(temporario, caminho)


def ordenar_saidas() -> None:
    """Deixa os arquivos finais em ordem de data, mantendo a ordem da página."""
    for caminho, colunas in ((ARQ_DATAS, COLUNAS_DATAS), (ARQ_REGISTROS, COLUNAS_REGISTROS)):
        if caminho.exists():
            with open(caminho, newline="", encoding="utf-8") as arquivo:
                linhas = list(csv.DictReader(arquivo))
            linhas.sort(key=lambda linha: linha["data"])  # sort é estável
            _reescrever(caminho, colunas, linhas)


def _abrir_para_acrescentar(caminho, colunas: list[str]):
    novo = not caminho.exists()
    arquivo = open(caminho, "a", newline="", encoding="utf-8")
    escritor = csv.writer(arquivo)
    if novo:
        escritor.writerow(colunas)
        arquivo.flush()
    return arquivo, escritor


def registrar_divergencia(escritor, arquivo, valores: list) -> None:
    escritor.writerow(valores)
    arquivo.flush()


def main() -> int:
    preparar_console()
    DIR_BRUTOS.mkdir(parents=True, exist_ok=True)

    feitas = recuperar_checkpoint()
    todas = list(datas_do_periodo())
    pendentes = [dia for dia in todas if dia.isoformat() not in feitas]
    print(f"CGE: {len(todas)} datas no período, {len(pendentes)} pendentes", flush=True)

    falhas: list[str] = []
    falhas_seguidas = 0
    divergencias = 0
    arq_reg, esc_reg = _abrir_para_acrescentar(ARQ_REGISTROS, COLUNAS_REGISTROS)
    arq_dat, esc_dat = _abrir_para_acrescentar(ARQ_DATAS, COLUNAS_DATAS)
    arq_div = None
    esc_div = None

    try:
        for indice, dia in enumerate(pendentes, start=1):
            try:
                pagina = coletar_dia(dia)
            except FalhaDeColeta as erro:
                # A data não entra no checkpoint: fica pendente para nova execução.
                falhas.append(f"{dia.isoformat()}: {erro}")
                print(f"FALHA {dia}: {erro}", flush=True)
                falhas_seguidas += 1
                if falhas_seguidas >= LIMITE_FALHAS_SEGUIDAS:
                    print(
                        f"Interrompido: {falhas_seguidas} falhas seguidas. "
                        "As datas restantes continuam pendentes; execute de novo mais tarde.",
                        flush=True,
                    )
                    break
                time.sleep(PAUSA_ENTRE_DIAS)
                continue

            falhas_seguidas = 0
            n_registros = len(pagina.registros)
            resumo_t = sum(pagina.resumo_transitaveis)
            resumo_i = sum(pagina.resumo_intransitaveis)
            soma_pts = sum(pagina.pts_declarados)

            # Os registros entram antes da data: é o que torna o checkpoint seguro.
            for registro in pagina.registros:
                esc_reg.writerow([dia.isoformat()] + [registro[c] for c in COLUNAS_REGISTROS[1:]])
            arq_reg.flush()

            situacao = "sem_registro" if pagina.sem_registro else "com_registro"
            agora = datetime.now().astimezone().isoformat(timespec="seconds")
            esc_dat.writerow([dia.isoformat(), situacao, n_registros, resumo_t, resumo_i, agora])
            arq_dat.flush()

            motivos = []
            if n_registros != resumo_t + resumo_i:
                motivos.append("registros != resumo lateral")
            if n_registros != soma_pts:
                motivos.append("registros != soma de pts por subprefeitura")
            if motivos:
                divergencias += 1
                if arq_div is None:
                    arq_div, esc_div = _abrir_para_acrescentar(ARQ_DIVERGENCIAS, COLUNAS_DIVERGENCIAS)
                registrar_divergencia(
                    esc_div, arq_div,
                    [dia.isoformat(), n_registros, resumo_t + resumo_i, soma_pts, "; ".join(motivos)],
                )

            if indice % 100 == 0 or indice == len(pendentes):
                print(f"  {indice}/{len(pendentes)} datas processadas (última: {dia})", flush=True)
            time.sleep(PAUSA_ENTRE_DIAS)
    finally:
        arq_reg.close()
        arq_dat.close()
        if arq_div is not None:
            arq_div.close()

    ordenar_saidas()
    print(f"CGE concluído. Falhas: {len(falhas)}. Divergências nesta execução: {divergencias}.", flush=True)
    for falha in falhas:
        print("  " + falha)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
