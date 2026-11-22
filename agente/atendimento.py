"""Agente de atendimento da Quantum Commerce, com as peças do Quantum Atende.

Roteador (LLM) → recuperação (BM25 sobre politicas/) → especialista (LLM).

O roteador usa o prompt do classificador do Quantum Atende (o multiagente LangGraph do grupo
"Tenho Medo de Grupos", disciplina Agents, Multi-Agents & Interoperability) e a recuperação usa a
busca BM25 dele (busca.py). O grafo completo não roda aqui: custa ~4,5 chamadas de LLM e ~32 mil
tokens por chamado, o que não cabe no agent gate de um runner gratuito. A função atender() devolve
o mesmo dicionário de sempre, que é o contrato com a esteira.
"""

import json
import os
import re
from functools import cache
from pathlib import Path

import busca
import llm

PASTA = Path(__file__).parent
CATEGORIAS = [
    "entrega",
    "divergente_defeito",
    "fraude_vendedor",
    "falsificado",
    "artigo_proibido",
    "devolucao_ressarcimento",
]
# Versão do prompt ativa — no GitOps (Aula 3) ela vem do inference-config
PROMPT_VERSAO = os.environ.get("PROMPT_VERSAO", "arquivo")


@cache
def politicas() -> dict[str, str]:
    return {a.name: a.read_text(encoding="utf-8") for a in sorted((PASTA / "politicas").glob("*.md"))}


def recuperar(chamado: str, categoria: str) -> dict:
    """RAG: BM25 sobre radicais, portado do Quantum Atende (busca.py).

    A política da categoria escolhida pelo roteador ganha reforço de área: é o
    sub-agente especialista consultando primeiro a sua própria política.
    """
    trecho = busca.buscar(chamado, categoria, politicas())
    return {"documento": trecho["documento"], "texto": trecho["texto"]}


@cache
def prompt(nome: str) -> str:
    """Lê o template. Com PROMPT_FONTE=mlflow, vem do Prompt Registry (Aula 5)."""
    if os.environ.get("PROMPT_FONTE") == "mlflow":
        import mlflow

        alias = os.environ.get("PROMPT_ALIAS", "producao")
        return mlflow.genai.load_prompt(f"prompts:/quantum-{nome}@{alias}").template
    return (PASTA / "prompts" / f"{nome}.txt").read_text(encoding="utf-8")


def preencher(template: str, **variaveis: str) -> str:
    for chave, valor in variaveis.items():
        template = template.replace("{{" + chave + "}}", valor)
    return template


def classificar(chamado: str) -> str:
    saida = llm.completar(preencher(prompt("roteador"), chamado=chamado), max_tokens=30)
    achado = re.search(r'"categoria"\s*:\s*"([a-z_]+)"', saida)
    categoria = achado.group(1) if achado else ""
    return categoria if categoria in CATEGORIAS else "indefinida"


def atender(chamado: str) -> dict:
    categoria = classificar(chamado)
    trecho = recuperar(chamado, categoria)
    resposta = llm.completar(
        preencher(
            prompt("especialista"),
            categoria=categoria,
            documento=trecho["documento"],
            contexto=trecho["texto"],
            chamado=chamado,
        ),
        max_tokens=160,
    )
    return {
        "categoria": categoria,
        "documento": trecho["documento"],
        "resposta": resposta.strip(),
        "prompt_versao": PROMPT_VERSAO,
        "modelo": f"{llm.PROVEDOR}:{llm.MODELO}",
    }


if __name__ == "__main__":
    import sys

    chamado = " ".join(sys.argv[1:]) or "Meu pedido está atrasado"
    print(json.dumps(atender(chamado), ensure_ascii=False, indent=2))
