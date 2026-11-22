"""Testes da busca BM25 portada do Quantum Atende: determinísticos, sem LLM."""

import csv

import pytest

import atendimento
import busca


def test_radical_por_truncamento_junta_as_flexoes():
    assert busca.termos("devolvi devolver devolução") == ["devol", "devol", "devol"]


def test_stopwords_e_acentos_saem():
    assert busca.termos("Não é o meu pedido") == ["pedid"]


@pytest.mark.parametrize(
    ("chamado", "esperado"),
    [
        ("o rastreio está parado há mais de uma semana", "entrega.md"),
        ("quero devolver, me arrependi da compra", "devolucao_ressarcimento.md"),
        ("o vendedor pediu pix por fora e sumiu", "fraude_vendedor.md"),
    ],
)
def test_acha_a_politica_so_pelo_texto(chamado, esperado):
    """Sem a categoria do roteador (categoria inexistente): o BM25 sozinho acha a política."""
    assert busca.buscar(chamado, "nenhuma", atendimento.politicas())["documento"] == esperado


def test_reforco_de_area_favorece_a_politica_da_categoria():
    politicas = atendimento.politicas()
    texto = "qual é o prazo?"
    for categoria in atendimento.CATEGORIAS:
        assert busca.buscar(texto, categoria, politicas)["documento"] == f"{categoria}.md"


def test_golden_de_politicas_com_a_categoria_certa():
    """Com a categoria anotada, a busca acha o documento anotado nos 36 casos."""
    with open(atendimento.PASTA / "golden" / "chamados.csv", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    erros = [
        linha["chamado"]
        for linha in linhas
        if atendimento.recuperar(linha["chamado"], linha["categoria"])["documento"] != linha["documento"]
    ]
    assert erros == []
