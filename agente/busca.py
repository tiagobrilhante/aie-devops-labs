"""Busca BM25 sobre radicais, portada do Quantum Atende (retrieval.py, ADR-08 e ADR-09 do grupo).

Mesmos parâmetros do original: BM25 com k1 = 1,2 e b = 0,75, radical por truncamento em 5 letras
("devolvi", "devolver" e "devolução" viram "devol"), stopwords do grupo, um trecho por seção (## ou ###)
e reforço suave por área: 1,5 para a política da categoria escolhida pelo roteador, 0,6 para as outras.

Em Python puro de propósito: a base daqui tem 6 políticas e o agente não precisa carregar o scikit-learn
em produção. O original indexa 44 documentos com CountVectorizer e filtros de público e vigência, que não
existem nesta base.
"""

import math
import re
import unicodedata
from collections import Counter
from functools import cache

K1, B, RADICAL = 1.2, 0.75, 5
REFORCO_AREA, FORA_DA_AREA = 1.5, 0.6

STOPWORDS = {
    "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn")
    for p in """a o as os um uma uns umas de do da dos das em no na nos nas por pelo
pela pelos pelas para pra com sem que se e ou mas mais muito muita já não foi era é sou estou está esta isso
esse essa este meu minha meus minhas me eu ele ela eles elas lhe seu sua seus suas ao aos à às como quando
onde qual quais porque pois também ainda até depois antes sobre entre há ter tem tinha tenho fazer feito
vocês você""".split()
}

# Vocabulário de busca por área do original (TERMOS_AREA e TERMOS_REVISAO), nas categorias daqui.
# Não é regra de negócio: só orienta a consulta.
TERMOS = {
    "entrega": "prazo prometido rastreio atraso investigação transportadora extravio entrega não recebida",
    "devolucao_ressarcimento": (
        "reembolso devolução arrependimento faixa de valor teto prazo meio de pagamento cupom aceite"
    ),
    "divergente_defeito": (
        "produto diferente do anunciado divergência defeito garantia prazo categoria fotos troca "
        "reembolso análise"
    ),
    "artigo_proibido": "item de venda não permitida denúncia conformidade anúncio brinde envio conjunto",
    "falsificado": "autenticidade imitação produto original denúncia fotos prazo reembolso integral",
    "fraude_vendedor": "disputa má-fé vendedor pagamento retido prevenção pagamento fora da plataforma",
}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def termos(texto: str) -> list[str]:
    return [p[:RADICAL] for p in re.findall(r"\w+", sem_acento(texto)) if p not in STOPWORDS]


def trechos(documento: str, texto: str) -> list[dict]:
    """Um trecho por seção; o título do documento entra em cada trecho, como o prefixo do original."""
    titulo = texto.splitlines()[0].lstrip("# ").strip() if texto.strip() else documento
    partes = [p.strip() for p in re.split(r"\n(?=#{2,3} )", texto) if p.strip()]
    return [{"documento": documento, "texto": p, "termos": termos(f"{titulo}\n{p}")} for p in partes]


@cache
def indice(politicas: tuple[tuple[str, str], ...]) -> tuple[list[dict], dict[str, float], float]:
    lista = [t for nome, texto in politicas for t in trechos(nome, texto)]
    df = Counter(termo for t in lista for termo in set(t["termos"]))
    n = len(lista)
    idf = {termo: math.log(1 + (n - d + 0.5) / (d + 0.5)) for termo, d in df.items()}
    media = sum(len(t["termos"]) for t in lista) / n
    return lista, idf, media


def pontuar(consulta: list[str], trecho: dict, idf: dict[str, float], media: float) -> float:
    tf = Counter(trecho["termos"])
    tamanho = len(trecho["termos"])
    return sum(
        idf.get(q, 0) * tf[q] * (K1 + 1) / (tf[q] + K1 * (1 - B + B * tamanho / media))
        for q in consulta
        if tf[q]
    )


def buscar(chamado: str, categoria: str, politicas: dict[str, str]) -> dict:
    """O documento do trecho com maior BM25 ponderado pela área (a política da categoria ganha reforço)."""
    lista, idf, media = indice(tuple(sorted(politicas.items())))
    consulta = termos(f"{chamado} {TERMOS.get(categoria, '')}")

    def pontos(trecho: dict) -> float:
        peso = REFORCO_AREA if trecho["documento"] == f"{categoria}.md" else FORA_DA_AREA
        return pontuar(consulta, trecho, idf, media) * peso

    melhor = max(lista, key=pontos)
    documento = melhor["documento"]
    return {"documento": documento, "texto": politicas[documento], "pontos": pontos(melhor)}
