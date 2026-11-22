"""Testes de dados (etapa 3 do pipeline): o lote pode virar modelo?

Por padrão testam a base de treino. Para testar o lote novo da Aula 2:

    DADOS=classificador/dados/lote-novo.csv pytest classificador/tests/test_dados.py

Regras que BLOQUEIAM ficam em assert; regras que só ALERTAM usam warnings
(aparecem no resumo do pytest, mas não reprovam).
"""

import os
import warnings
from pathlib import Path

import pandas as pd
import pytest

from texto import limpar, so_emojis

PASTA = Path(__file__).parent.parent / "dados"
CLASSES = {"positiva", "negativa", "neutra"}

# Distribuição de referência: a base que gerou o modelo em produção
REFERENCIA = {"positiva": 0.40, "negativa": 0.35, "neutra": 0.25}
DESVIO_ALERTA = 0.05  # classe 5 p.p. fora da referência → alerta
DESVIO_BLOQUEIO = 0.10  # classe 10 p.p. fora → bloqueia
MAX_SO_EMOJIS = 0.10  # mais de 10% de textos sem palavra → bloqueia

# Tamanho do texto: média de palavras (depois da mesma limpeza do modelo) na base de treino
# avaliacoes.csv. O ruído da média num lote de 300 linhas (bootstrap da base) fica abaixo de 7%
# em 99% dos casos; o lote-novo.csv está a −28%. O ±30% do enunciado deixaria esse lote passar.
MEDIA_PALAVRAS_REFERENCIA = 11.15
DESVIO_TAMANHO_ALERTA = 0.10  # média 10% fora da referência → alerta
DESVIO_TAMANHO_BLOQUEIO = 0.20  # média 20% fora → bloqueia


@pytest.fixture(scope="module")
def dados() -> pd.DataFrame:
    return pd.read_csv(os.environ.get("DADOS", PASTA / "avaliacoes.csv"))


def test_schema(dados):
    assert list(dados.columns) == ["texto", "rotulo"]


def test_sem_texto_vazio(dados):
    assert dados["texto"].fillna("").str.strip().ne("").all()


def test_rotulos_validos(dados):
    assert set(dados["rotulo"]) <= CLASSES


def test_volume_minimo(dados):
    assert len(dados) >= 300, f"só {len(dados)} linhas — pouco para retreinar"


def test_proporcao_de_textos_so_com_emojis(dados):
    frac = dados["texto"].map(so_emojis).mean()
    assert frac <= MAX_SO_EMOJIS, f"{frac:.0%} dos textos só têm emojis (máx. {MAX_SO_EMOJIS:.0%})"


@pytest.mark.parametrize("classe", sorted(CLASSES))
def test_distribuicao_das_classes(dados, classe):
    frac = (dados["rotulo"] == classe).mean()
    desvio = abs(frac - REFERENCIA[classe])
    if desvio > DESVIO_ALERTA:
        warnings.warn(f"classe '{classe}' em {frac:.0%} (referência {REFERENCIA[classe]:.0%})")
    assert desvio <= DESVIO_BLOQUEIO, (
        f"classe '{classe}' em {frac:.0%}, referência {REFERENCIA[classe]:.0%} — drift de rótulo"
    )


def test_tamanho_medio_do_texto(dados):
    media = dados["texto"].map(lambda t: len(limpar(t).split())).mean()
    desvio = media / MEDIA_PALAVRAS_REFERENCIA - 1
    if abs(desvio) > DESVIO_TAMANHO_ALERTA:
        warnings.warn(f"média de {media:.1f} palavras por texto ({desvio:+.0%} da referência)")
    assert abs(desvio) <= DESVIO_TAMANHO_BLOQUEIO, (
        f"média de {media:.1f} palavras por texto, referência {MEDIA_PALAVRAS_REFERENCIA} "
        f"({desvio:+.0%}) — drift de tamanho"
    )
