"""Gera a tabela das 32 subprefeituras e o mapa de nomes CGE para GeoSampa.

Saídas em ml/dados/brutos:

  subprefeituras_geosampa.csv     limites oficiais (GeoSampa), centroide e elevação
  mapa_nomes_cge_geosampa.csv     de cada nome usado pelo CGE para o nome oficial

O centroide é calculado pela fórmula do polígono, descontando buracos e tratando
MultiPolygon, sem depender de bibliotecas geoespaciais. A elevação vem da
Elevation API da Open-Meteo, no ponto do centroide.

O mapa de nomes é uma lista conferida à mão. Se o CGE usar um nome que não esteja
na lista, o script para e mostra o nome: nada é adivinhado.

Depende de ml/dados/brutos/cge_alagamentos_2023_2025.csv (coletar_cge.py).

Uso: python coletar_subprefeituras.py [--refazer]
"""
from __future__ import annotations

import csv
import json
import os
import sys
import unicodedata
from collections import Counter
from urllib.parse import urlencode

from comum import DIR_BRUTOS, baixar, dir_temporario, preparar_console

URL_WFS = (
    "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs?"
    "service=WFS&version=2.0.0&request=GetFeature&typeNames=geoportal:subprefeitura"
    "&outputFormat=application/json&srsName=EPSG:4326"
)
URL_ELEVACAO = "https://api.open-meteo.com/v1/elevation"

ARQ_CGE = DIR_BRUTOS / "cge_alagamentos_2023_2025.csv"
ARQ_SUBPREFEITURAS = DIR_BRUTOS / "subprefeituras_geosampa.csv"
ARQ_MAPA = DIR_BRUTOS / "mapa_nomes_cge_geosampa.csv"

COLUNAS = [
    "subprefeitura", "nome_exibicao", "sigla", "regiao5", "regiao8",
    "area_km2", "lat_centroide", "lon_centroide", "elevacao_m",
]

# Nome com acentos usado só quando a subprefeitura não aparece nos registros do CGE.
NOME_COM_ACENTO = {
    "ARICANDUVA-FORMOSA-CARRAO": "Aricanduva/Formosa/Carrão",
    "BUTANTA": "Butantã",
    "CAMPO LIMPO": "Campo Limpo",
    "CAPELA DO SOCORRO": "Capela do Socorro",
    "CASA VERDE-LIMAO-CACHOEIRINHA": "Casa Verde/Limão/Cachoeirinha",
    "CIDADE ADEMAR": "Cidade Ademar",
    "CIDADE TIRADENTES": "Cidade Tiradentes",
    "ERMELINO MATARAZZO": "Ermelino Matarazzo",
    "FREGUESIA-BRASILANDIA": "Freguesia do Ó/Brasilândia",
    "GUAIANASES": "Guaianases",
    "IPIRANGA": "Ipiranga",
    "ITAIM PAULISTA": "Itaim Paulista",
    "ITAQUERA": "Itaquera",
    "JABAQUARA": "Jabaquara",
    "JACANA-TREMEMBE": "Jaçanã/Tremembé",
    "LAPA": "Lapa",
    "M BOI MIRIM": "M'Boi Mirim",
    "MOOCA": "Mooca",
    "PARELHEIROS": "Parelheiros",
    "PENHA": "Penha",
    "PERUS-ANHANGUERA": "Perus/Anhanguera",
    "PINHEIROS": "Pinheiros",
    "PIRITUBA-JARAGUA": "Pirituba/Jaraguá",
    "SANTANA-TUCURUVI": "Santana/Tucuruvi",
    "SANTO AMARO": "Santo Amaro",
    "SAO MATEUS": "São Mateus",
    "SAO MIGUEL": "São Miguel Paulista",
    "SAPOPEMBA": "Sapopemba",
    "SE": "Sé",
    "VILA MARIA-VILA GUILHERME": "Vila Maria/Vila Guilherme",
    "VILA MARIANA": "Vila Mariana",
    "VILA PRUDENTE": "Vila Prudente",
}

# Nome do CGE (sem acentos, em maiúsculas, espaços simples) -> nome oficial do GeoSampa.
# A lista é preenchida com os nomes realmente encontrados no CGE e conferida à mão.
MAPA_CGE = {
    "ARICANDUVA/ VILA FORMOSA": "ARICANDUVA-FORMOSA-CARRAO",
    "BUTANTA": "BUTANTA",
    "CAMPO LIMPO": "CAMPO LIMPO",
    "CAPELA DO SOCORRO": "CAPELA DO SOCORRO",
    "CASA VERDE": "CASA VERDE-LIMAO-CACHOEIRINHA",
    "CIDADE ADEMAR": "CIDADE ADEMAR",
    "CIDADE TIRADENTES": "CIDADE TIRADENTES",
    "ERMELINO MATARAZZO": "ERMELINO MATARAZZO",
    "FREGUESIA DO O": "FREGUESIA-BRASILANDIA",
    "GUAIANASES": "GUAIANASES",
    "IPIRANGA": "IPIRANGA",
    "ITAIM PAULISTA": "ITAIM PAULISTA",
    "ITAQUERA": "ITAQUERA",
    "JABAQUARA": "JABAQUARA",
    "JACANA/ TREMEMBE": "JACANA-TREMEMBE",
    "LAPA": "LAPA",
    "M'BOI MIRIM": "M BOI MIRIM",
    "MOOCA": "MOOCA",
    "PARELHEIROS": "PARELHEIROS",
    "PENHA": "PENHA",
    "PERUS": "PERUS-ANHANGUERA",
    "PINHEIROS": "PINHEIROS",
    "PIRITUBA/JARAGUA": "PIRITUBA-JARAGUA",
    "SANTANA": "SANTANA-TUCURUVI",
    "SANTO AMARO": "SANTO AMARO",
    "SAO MATEUS": "SAO MATEUS",
    "SAO MIGUEL PAULISTA": "SAO MIGUEL",
    "SAPOPEMBA": "SAPOPEMBA",
    "SE": "SE",
    "VILA MARIA/ VILA GUILHERME": "VILA MARIA-VILA GUILHERME",
    "VILA MARIANA": "VILA MARIANA",
    "VILA PRUDENTE": "VILA PRUDENTE",
}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.upper().split())


def area_centroide_anel(anel: list[list[float]]) -> tuple[float, float, float]:
    """Área (absoluta) e centroide de um anel, em graus.

    As coordenadas são deslocadas para o primeiro vértice para reduzir o erro de
    arredondamento da fórmula.
    """
    x0, y0 = anel[0][0], anel[0][1]
    soma_a = soma_x = soma_y = 0.0
    for (xa, ya, *_), (xb, yb, *_) in zip(anel, anel[1:]):
        xa, ya, xb, yb = xa - x0, ya - y0, xb - x0, yb - y0
        cruzado = xa * yb - xb * ya
        soma_a += cruzado
        soma_x += (xa + xb) * cruzado
        soma_y += (ya + yb) * cruzado
    area = soma_a / 2.0
    if area == 0:
        return 0.0, x0, y0
    return abs(area), x0 + soma_x / (6.0 * area), y0 + soma_y / (6.0 * area)


def centroide(geometria: dict) -> tuple[float, float]:
    """Centroide (lon, lat) de um Polygon ou MultiPolygon, descontando buracos."""
    if geometria["type"] == "Polygon":
        poligonos = [geometria["coordinates"]]
    elif geometria["type"] == "MultiPolygon":
        poligonos = geometria["coordinates"]
    else:
        raise ValueError(f"Geometria não suportada: {geometria['type']}")

    area_total = soma_x = soma_y = 0.0
    for aneis in poligonos:
        for indice, anel in enumerate(aneis):
            area, cx, cy = area_centroide_anel(anel)
            sinal = 1.0 if indice == 0 else -1.0  # o primeiro anel é o contorno
            area_total += sinal * area
            soma_x += sinal * area * cx
            soma_y += sinal * area * cy
    return soma_x / area_total, soma_y / area_total


def carregar_geojson(refazer: bool = False) -> dict:
    cache = dir_temporario("geosampa") / "subprefeituras.geojson"
    if refazer or not cache.exists():
        cache.write_bytes(baixar(URL_WFS, timeout=180))
    return json.loads(cache.read_bytes().decode("utf-8"))


def buscar_elevacoes(latitudes: list[float], longitudes: list[float]) -> list[float]:
    """Consulta a elevação de todos os centroides (até 100 pontos por chamada)."""
    consulta = urlencode({
        "latitude": ",".join(f"{v:.6f}" for v in latitudes),
        "longitude": ",".join(f"{v:.6f}" for v in longitudes),
    }, safe=",")
    resposta = json.loads(baixar(f"{URL_ELEVACAO}?{consulta}").decode("utf-8"))
    return resposta["elevation"]


def nomes_cge() -> Counter:
    """Conta quantos registros existem para cada nome usado pelo CGE."""
    with open(ARQ_CGE, newline="", encoding="utf-8") as arquivo:
        return Counter(linha["subprefeitura_cge"] for linha in csv.DictReader(arquivo))


def gravar(caminho, colunas, linhas) -> None:
    temporario = caminho.with_name(caminho.name + ".tmp")
    with open(temporario, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)
    os.replace(temporario, caminho)


def main() -> int:
    preparar_console()
    if ARQ_SUBPREFEITURAS.exists() and ARQ_MAPA.exists() and "--refazer" not in sys.argv[1:]:
        with open(ARQ_MAPA, newline="", encoding="utf-8") as arquivo:
            ja_mapeados = {linha["subprefeitura_cge"] for linha in csv.DictReader(arquivo)}
        if set(nomes_cge()) <= ja_mapeados:
            print("Subprefeituras: arquivos já existem e cobrem todos os nomes do CGE; nada a fazer", flush=True)
            return 0

    feicoes = carregar_geojson("--refazer" in sys.argv[1:])["features"]
    if len(feicoes) != 32:
        print(f"ERRO: esperadas 32 subprefeituras, vieram {len(feicoes)}", flush=True)
        return 1
    oficiais = {f["properties"]["nm_subprefeitura"] for f in feicoes}
    if set(NOME_COM_ACENTO) != oficiais:
        print(f"ERRO: nomes oficiais diferentes do esperado: {set(NOME_COM_ACENTO) ^ oficiais}", flush=True)
        return 1

    # Mapa de nomes: cada nome do CGE precisa estar na lista conferida.
    contagem = nomes_cge()
    nao_mapeados = {n: c for n, c in contagem.items() if normalizar(n) not in MAPA_CGE}
    if nao_mapeados:
        print("ERRO: nomes do CGE sem mapeamento conferido:", flush=True)
        for nome, total in sorted(nao_mapeados.items()):
            print(f"  {nome!r}: {total} registros", flush=True)
        return 1
    invalidos = {v for v in MAPA_CGE.values() if v not in oficiais}
    if invalidos:
        print(f"ERRO: destinos que não são subprefeituras oficiais: {invalidos}", flush=True)
        return 1

    mapa = [
        {"subprefeitura_cge": nome, "subprefeitura": MAPA_CGE[normalizar(nome)]}
        for nome in sorted(contagem)
    ]
    gravar(ARQ_MAPA, ["subprefeitura_cge", "subprefeitura"], mapa)

    # Nome de exibição: o nome mais frequente no CGE; sem registros, o nome com acentos.
    exibicao: dict[str, str] = {}
    for nome, total in contagem.most_common():
        exibicao.setdefault(MAPA_CGE[normalizar(nome)], nome)

    linhas = []
    for feicao in sorted(feicoes, key=lambda f: f["properties"]["nm_subprefeitura"]):
        props = feicao["properties"]
        lon, lat = centroide(feicao["geometry"])
        nome = props["nm_subprefeitura"]
        linhas.append({
            "subprefeitura": nome,
            "nome_exibicao": exibicao.get(nome, NOME_COM_ACENTO[nome]),
            "sigla": props["sg_subprefeitura"],
            "regiao5": props["nm_regiao_05"],
            "regiao8": props["nm_regiao_08"],
            "area_km2": round(props["qt_area_metro"] / 1e6, 3),
            "lat_centroide": round(lat, 6),
            "lon_centroide": round(lon, 6),
        })

    elevacoes = buscar_elevacoes([l["lat_centroide"] for l in linhas], [l["lon_centroide"] for l in linhas])
    for linha, elevacao in zip(linhas, elevacoes):
        linha["elevacao_m"] = elevacao

    gravar(ARQ_SUBPREFEITURAS, COLUNAS, linhas)
    print(f"Subprefeituras concluídas: {len(linhas)} linhas; mapa com {len(mapa)} nomes do CGE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
