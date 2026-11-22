"""Ponte entre o promptfoo e o roteador: no golden de roteamento, só a classificação conta.

Mede o roteador sem gastar a chamada do especialista: 1 chamada de LLM por caso.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import atendimento  # noqa: E402


def call_api(prompt, options, context):
    try:
        categoria = atendimento.classificar(context["vars"]["chamado"])
    except Exception as erro:  # o erro vira resultado reprovado, não derruba a avaliação inteira
        return {"error": f"{type(erro).__name__}: {erro}"}
    return {"output": json.dumps({"categoria": categoria}, ensure_ascii=False)}
