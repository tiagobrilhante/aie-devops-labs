"""Compara roteadores no golden de roteamento: 180 reclamações do chamados-200.csv (sem a classe 'outros').

    python roteamento_180.py <roteador.txt> <saida.json>
"""
import csv, json, os, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "agente")
import atendimento  # noqa: E402

# CSV do grupo (repositório do Quantum Atende, ao lado deste)
CSV = os.environ.get("CHAMADOS_CSV", "../MultiAgentsAndInteroperability/dados/chamados-200.csv")
roteador = Path(sys.argv[1]).read_text(encoding="utf-8")
original = atendimento.prompt
atendimento.prompt = lambda nome: roteador if nome == "roteador" else original(nome)

linhas = [l for l in csv.DictReader(open(CSV, encoding="utf-8"), delimiter=";") if l["classe"] != "outros"]
inicio = time.time()
with ThreadPoolExecutor(2) as ex:  # mesma concorrência do promptfooconfig
    previstas = list(ex.map(lambda l: atendimento.classificar(l["texto_reclamacao"]), linhas))
acertos, total, confusao = defaultdict(int), Counter(), Counter()
for l, p in zip(linhas, previstas):
    total[l["classe"]] += 1
    acertos[l["classe"]] += p == l["classe"]
    if p != l["classe"]:
        confusao[(l["classe"], p)] += 1
res = {"roteador": sys.argv[1], "segundos": round(time.time() - inicio, 1),
       "acuracia": round(sum(acertos.values()) / len(linhas), 3),
       "por_categoria": {c: round(acertos[c] / total[c], 3) for c in sorted(total)},
       "confusoes": {f"{a} → {b}": n for (a, b), n in confusao.most_common()},
       "casos": [{"id": l["id_reclamacao"], "esperada": l["classe"], "prevista": p} for l, p in zip(linhas, previstas)]}
Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "casos"}, ensure_ascii=False, indent=1))
