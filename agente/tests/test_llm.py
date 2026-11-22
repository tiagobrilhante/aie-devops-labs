"""Testes do provedor anthropic com um cliente falso: sem rede e sem chave."""

from types import SimpleNamespace

import pytest

import llm


class ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.resposta


def resposta(stop_reason="end_turn", *blocos):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocos))


def texto(t):
    return SimpleNamespace(type="text", text=t)


@pytest.fixture
def anthropic_falso(monkeypatch):
    def instalar(r):
        cliente = ClienteFalso(r)
        monkeypatch.setattr(llm, "PROVEDOR", "anthropic")
        monkeypatch.setattr(llm, "MODELO", "claude-haiku-5-5")
        monkeypatch.setattr(llm, "_cliente_anthropic", cliente)
        return cliente

    return instalar


def test_junta_so_os_blocos_de_texto(anthropic_falso):
    pensamento = SimpleNamespace(type="thinking", thinking="")
    cliente = anthropic_falso(resposta("end_turn", pensamento, texto('{"categoria": '), texto('"entrega"}')))
    assert llm.completar("Chamado: atrasou", max_tokens=30) == '{"categoria": "entrega"}'
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-haiku-5-5"
    assert chamada["max_tokens"] >= llm.MAX_TOKENS_ANTHROPIC  # o pensamento não pode cortar a resposta
    assert chamada["output_config"] == {"effort": "low"}
    assert "temperature" not in chamada and "seed" not in chamada  # os modelos atuais rejeitam


def test_esforco_vem_do_ambiente(anthropic_falso, monkeypatch):
    cliente = anthropic_falso(resposta("end_turn", texto("ok")))
    monkeypatch.setenv("LLM_ESFORCO", "medium")
    llm.completar("oi")
    assert cliente.chamadas[0]["output_config"] == {"effort": "medium"}


def test_recusa_vira_resposta_vazia(anthropic_falso):
    anthropic_falso(resposta("refusal"))
    assert llm.completar("oi") == ""
