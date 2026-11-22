# Entregáveis 3 a 6 — esqueleto (rascunho)

> Rascunho. Os nomes dos entregáveis vêm do `roteiros/aula-06.md` (*"os entregáveis 3 a 6 estão no documento"*). O
> documento, com o conteúdo exigido de cada um, só sai no começo da Aula 6. Tudo abaixo é **a confirmar com o enunciado
> da Aula 6**.

## Entregável 3 — `gitops/` (repositório de configuração)

**O que já existe neste repositório** (testado na Aula 3, `../aula3/README.md`):

| Peça | Arquivo | Estado |
| --- | --- | --- |
| Base comum | `gitops/base/agente-suporte/` (`deployment.yaml`, `service.yaml`, `inference-config.env`) | a configuração de inferência fica versionada: `MODELO`, `PROMPT_VERSAO`, `TEMPERATURA`, `MAX_TOKENS`, `RAG_INDICE`, `TIMEOUT_SEGUNDOS` |
| Ambientes | `gitops/overlays/staging/` e `gitops/overlays/producao/` | só o que difere da base; o `diff` dos dois responde "o que ainda não foi promovido" |
| Argo CD | `gitops/apps/agente-{staging,producao}.yaml` | `selfHeal: true` nos dois (produção mudou no PR #8) |
| Policy-as-code no PR | `gitops/politicas/verificar.py` + `gitops-pr.yml` | versão explícita (nada de `latest`), sem segredo em texto claro, produção com ≥ 2 réplicas |
| Revisão | `.github/CODEOWNERS` com regra para `/gitops/overlays/producao/` | ativo |

**Medido:** promoção pelo Git em **16 s** do merge ao deploy; rollback por `git revert` em **20 s**; drift detectado na
hora; staging se cura em < 3 s.

**O que o grupo precisa mudar** (*a confirmar com o enunciado da Aula 6*):

1. **A imagem:** hoje é um `hashicorp/http-echo` que só ecoa a configuração. Trocar pela imagem do agente real (o Quantum
   Atende em integração leve, PR #11).
2. **O segredo do LLM:** o check barra a chave no `ConfigMap`, mas não há o caminho certo. Falta um `Secret` externo
   (Sealed Secrets ou External Secrets).
3. **Os `Application` fora do Git:** o merge do `selfHeal` não chegou ao cluster (problema 1 da Aula 3). Um *app of apps*
   que observe `gitops/apps/` resolve.
4. **A configuração do agente real:** `MODELO`, `PROMPT_VERSAO` e `RAG_INDICE` precisam corresponder ao que o agent gate
   aprovou (problema 7 da Aula 6: o gate aprovou um LLM e a produção rodou outro).

## Entregável 4 — estratégia de rollout

Rascunho em [`aula4-propostas-de-rollout.md`](aula4-propostas-de-rollout.md). Para o agente da Quantum, o cenário 2:
agent gate no PR → canary por sessão atrás de um feature toggle, com métricas **por categoria** e amostra mínima.
O canary da Aula 4 rodou no Azure (slots do App Service): a lição principal é aquecer a candidata antes de
medir latência. *A confirmar com o enunciado da Aula 6.*

## Entregável 5 — book de métricas

| Métrica | Fórmula | Fonte | Limite | Quem age |
| --- | --- | --- | --- | --- |
| Textos só com emoji | linhas sem palavra depois de `limpar` ÷ total | `test_dados.py` | ≤ 10% | o pipeline bloqueia; dados investiga o lote |
| Desvio de classe | \|fração da classe − referência\| | `test_dados.py` | alerta > 5 p.p.; bloqueia > 10 p.p. | o pipeline |
| Desvio do tamanho médio | média de palavras ÷ 11,15 − 1 | `test_dados.py` (PR #10) | alerta > 10%; bloqueia > 20% | o pipeline |
| F1 macro do candidato | F1 macro na validação | `model_gate.py` | ≥ 0,80 | o pipeline bloqueia o deploy |
| F1 por classe | F1 de cada classe | `model_gate.py` | ≥ 0,70 | o pipeline |
| Queda em relação à produção | F1 de produção − F1 do candidato | `model_gate.py` | ≤ 0,02 | o pipeline |
| Erro do canary | respostas 5xx ÷ requisições no canary | `canary_check.py` | ≤ 2% e ≤ +1 p.p. sobre o estável | rollback automático |
| Latência do canary | p95 do canary ÷ p95 do estável | `canary_check.py` | ≤ 1,5 | rollback automático |
| Distribuição das previsões | \|fração por rótulo, canary − estável\| | `canary_check.py` | ≤ 15 p.p. | rollback automático |
| Amostra mínima do canary | requisições no canary | *proposta* | ≥ ~150 antes de decidir | o workflow espera |
| Agent gate por categoria e camada | acertos ÷ casos (roteamento, recuperação, resposta) | `agent_gate.py` + `limites.yaml` | ≥ 50% e queda ≤ 0,34 em relação à baseline | bloqueia o PR; override só com rótulo |
| Fidelidade (juiz) | casos sem contradição ÷ casos | `juiz_resumo.py` | ≥ 0,66 (hoje só informa) | o time revisa |
| Overrides do gate | PRs liberados com `override-agent-gate` | resumo do workflow | 0 esperado; cada um justificado | o *code owner* |
| Drift | tempo com app `OutOfSync` em produção | Argo CD | 0 (`selfHeal: true`) | o Argo CD desfaz; o SRE investiga quem mudou |
| Lead time de configuração | merge → deploy | histórico do Argo CD | medido: 16 s | — |
| Tempo de rollback | merge do revert → produção | histórico do Argo CD | medido: 20 s | — |
| Custo por chamado | tokens de entrada e saída por chamado | logs do agente | *a definir*; o grafo completo do Quantum Atende mediu ~32 mil tokens de entrada | o time do agente |
| Custo de infra | preço/hora do plano | API de preços do Azure | B1 Linux US$ 0,02/h; S1 Linux US$ 0,116/h (brazilsouth) | apagar ao fim de cada teste |
| Escalonamento para humano | conversas escalonadas ÷ conversas, **por categoria** | *não instrumentado* | *a definir* | rollback do canary |

*A confirmar com o enunciado da Aula 6:* o formato do "book" (documento, painel?) e quais métricas são obrigatórias.

## Entregável 6 — pitch

Duração e formato **não aparecem nos slides** (só *"a Aula 6 fecha o módulo com o laboratório e o pitch finais"*,
Aula 00, p. 18). Estrutura sugerida:

1. **O problema:** atualizar o agente da Quantum sem quebrar o atendimento; a regressão de prompt é silenciosa.
2. **A esteira:** o diagrama (Aula 2) com o agent gate como etapa 5.
3. **A demonstração:** um PR que piora o prompt é barrado pelo gate; o override fica registrado (PR #7).
4. **Os números que medimos:** 16 s para promover, 20 s para reverter, a queda escondida pela média (variante D),
   os rollbacks falsos do canary.
5. **O que ainda não resolvemos:** juiz fraco, golden pequeno (6 casos por categoria), LLM do gate ≠ LLM de produção.
6. **Próximos passos.**

*A confirmar com o enunciado da Aula 6.*
