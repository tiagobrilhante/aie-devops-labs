# Integração do Quantum Atende no agent gate (PR #11)

Registro de 22/11/2026. O roteiro da Aula 6 pede: *"no capstone, troque pelo multiagente do seu grupo mantendo
`atender()`"*. O multiagente do grupo "Tenho Medo de Grupos" é o **Quantum Atende** (LangGraph, disciplina *Agents,
Multi-Agents & Interoperability*), em `Workspace/fiap/MultiAgentsAndInteroperability`, commit `c721dd3`, sem remote. A
publicação no repositório público foi combinada com o grupo.

## 1. Por que a integração é "leve"

O grafo completo (classificador → orquestrador com *function calling* → especialista ReAct com RAG → síntese) custa, nos
números do próprio grupo (`evidencias/avaliacao-base-200-v4/resumo.md`, medido com o Claude), **~4,5 chamadas de LLM e
~32 mil tokens de entrada por chamado**, com mediana de 29 s. Com o `qwen2.5:3b` num runner de 2 vCPU só CPU, os 36 casos
do gate não caberiam no job. Os dois projetos também não convivem num ambiente só: o Quantum Atende usa `openai` 3.16 e
LangChain/LangGraph 1.x, e o agente daqui usa `openai` 1.82.

Por isso entram **duas peças**, portadas, e o resto do agente fica igual:

| Peça | De onde | Como entrou |
| --- | --- | --- |
| Roteador | `classifier.py` (as definições de fronteira e as regras do prompt v2) | `agente/prompts/roteador.txt`, pelo caminho normal de mudança de prompt (PR, CODEOWNERS, agent gate, Prompt Registry) |
| Recuperação | `retrieval.py` (BM25 sobre radicais, ADR-08 e ADR-09) | `agente/busca.py`, em Python puro (a base daqui tem 6 políticas; produção não precisa do scikit-learn) |

## 2. As medições (locais, `qwen2.5:3b`, Apple Silicon; 3 execuções idênticas)

**Roteador:**

| Roteador | 36 dúvidas de política (golden do template) | 180 reclamações reais (golden do grupo) | Tokens do prompt |
| --- | --- | --- | --- |
| Template (antes) | **86%** | 76,1% | 286 |
| Grupo, com os 15 exemplos (`CLASSIFIER_FEWSHOT=True`) | 75% | 88,3% | 1.669 |
| **Grupo, sem exemplos (`CLASSIFIER_FEWSHOT=False`, o PR)** | 75% | **91,1%** | 767 |
| Grupo, sem exemplos + uma regra para dúvidas de processo (descartado) | 69% | 89,4% | ~800 |

Por categoria, nas 180 reclamações:

| Categoria | Template | Grupo, sem exemplos |
| --- | --- | --- |
| artigo_proibido | 90% | 93% |
| devolucao_ressarcimento | 73% | 83% |
| divergente_defeito | 97% | 87% |
| entrega | 80% | 100% |
| **falsificado** | **43%** | **93%** |
| fraude_vendedor | 73% | 90% |

**Recuperação** (a categoria vem do golden, então não há efeito do roteador):

| Busca | Com a categoria certa | Só pelo texto |
| --- | --- | --- |
| Antiga (palavras em comum + bônus 3) | 36/36 | 17/36 |
| **BM25 do Quantum Atende** | 36/36 | **26/36** |

## 3. As decisões (e por quê)

1. **O prompt vai sem os exemplos.** Ele acerta tanto quanto ou mais (91,1% × 88,3%) e usa menos da metade dos tokens,
   o que pesa no runner de CPU. É uma configuração prevista pelo próprio Quantum Atende. Os exemplos foram feitos para
   o modelo grande do grupo, e com o modelo de 3B eles atrapalham. Se a produção usar um modelo grande, vale medir de novo
   **com** eles.
2. **O gate passa a ter dois goldens.**
   - As 36 dúvidas continuam medindo as três camadas.
   - As 180 reclamações medem só o roteamento, com baseline e limites próprios: piso de 60% e tolerância de 15 p.p.
     (~5 casos), a calibrar no runner.
   - Medir o roteador só pelas dúvidas faria o gate rejeitar o agente que vai melhor no tráfego real.
3. **A queda de `falsificado` nas 36 dúvidas é aceita com override justificado.**
   - O roteador do grupo manda dúvidas de processo ("quem paga o frete da perícia?", "quanto tempo demora a análise de
     produto pirata?") para `outros`, que no Quantum Atende significa **atendente humano**. Errar para um humano é mais
     seguro que errar para o especialista errado.
   - Tentei **uma** regra geral para esse caso e ela piorou os dois goldens (linha descartada na tabela). Não continuei
     ajustando o prompt: isso é decisão do grupo, e ajuste em cima do golden vira *overfitting*.
4. **A baseline nova vem do runner, não do Mac.** O ruído depende do hardware (ver o relatório da Aula 6).

## 4. No runner do GitHub: PR #11, merge e baselines (PR #12)

| Execução (mesmo código) | Políticas: roteamento · recuperação · resposta | Roteamento (180) |
| --- | --- | --- |
| PR #11, 1ª (run 45048329304) | 83% · 83% · 75%, ❌ por `falsificado` | 92% ✅ |
| PR #11, com o rótulo `override-agent-gate` (45050007716) | 83% · 83% · 83%, ⚠️ liberado por override | 91% ✅ |
| `main` depois do merge, `e2535a8` (45055797316) | 81% · 81% · 75%, ❌ (sem override no push; o deploy foi pulado) | 89% ✅ |

- **Tempos no runner:** golden de políticas em ~5 a 8 min, golden de roteamento em ~8 a 13 min, job inteiro em ~16 a 23
  min. O limite de 45 min deixa folga.
- **Ruído medido** (`evidencias/runner/ruido-3-execucoes-runner.txt`):
  - golden de políticas: no roteamento e na recuperação, até 1 caso; na resposta, até **2 casos de 6** (33 p.p.);
  - golden de roteamento: até **2 casos de 30** (7 p.p.). A tolerância de 15 p.p. e o piso de 60% ficam com folga de ~2×.
- **Baselines** (PR #12): salvas a partir da execução na `main`, como manda o `agent_gate.py`. **Risco conhecido:**
  `artigo_proibido/resposta` e as três camadas de `falsificado` ficaram em 50%, exatamente no piso. Com 2 casos de ruído
  na resposta, um PR futuro pode reprovar ali sem mudança real. A solução está com o grupo: mais casos por categoria no
  golden de políticas, ou um piso de resposta menor.
- **Um alarme falso meu, registrado:** no JSON do promptfoo, o campo `error` também guarda a mensagem de asserção
  reprovada ("Custom function returned false"). Os "19 erros" que vi primeiro eram respostas erradas, não falhas de
  execução.

## 5. Trocando o LLM: Claude Haiku 5.5 (PR #13)

O `qwen2.5:3b` no runner tinha três problemas: o gate aprovava um modelo que não ia para produção (o Web App não roda
Ollama), ele oscilava até 2 casos de 6 entre execuções idênticas e levava de 16 a 23 min por PR. O PR #13 acrescenta o
provedor `anthropic` (SDK oficial, `anthropic==2.6.0`) e deixa a OpenAI prevista (`OPENAI_API_KEY`, `.env.example`).
A escolha passa a ser por variável do repositório.

| | `qwen2.5:3b` (baseline do runner, PR #12) | **Claude Haiku 5.5** (local, mesma API do runner) |
| --- | --- | --- |
| Dúvidas de política: roteamento · recuperação · resposta | 81% · 81% · 75% | **89% · 97% · 97%** |
| `falsificado` nas dúvidas | 50% | **100%** |
| Reclamações reais (roteamento) | 89% | **98%** |
| Tempo dos dois goldens | ~13 a 20 min (runner) | ~2 min 40 s |
| Custo por execução | zero | ~US$ 0,03 (estimado: ~250 chamadas × ~1,1 mil tokens a US$ 0,10/milhão) |

- **A queda de `falsificado` que justificou o override do PR #11 some com o Haiku.** Era limitação do modelo de 3B, não
  do roteador do grupo.
- Com o esforço `low`, o roteador respondeu sem "pensar": 1.116 tokens de entrada e 14 de saída numa chamada
  (`request_id req_011ChJWMDDXzFRN867XsqjHC`).
- Os modelos atuais da Anthropic não aceitam `temperature` nem `seed`. O ruído entre execuções precisa ser medido de
  novo antes de calibrar a tolerância.

Evidências: `evidencias/haiku-local/` (os dois evals, os logs e as tabelas do gate).

**No runner, depois do merge do #13** (variáveis `LLM_PROVEDOR=anthropic` e `LLM_MODELO=claude-haiku-5-5`, secret
`ANTHROPIC_API_KEY`), em três execuções do mesmo código (runs 45061750891, 45062220165 e 45062227053):

- **Job inteiro em ~4 min** (antes, de 16 a 23). As etapas do Ollama são puladas.
- **Políticas:** roteamento de 89% a 94%; recuperação e resposta de 97% a 100%. Ainda há variação de até 2 casos de 6
  (`fraude_vendedor`), porque 6 casos por categoria é pouco.
- **Reclamações reais:** de 98% a 99%, com variação de **1 caso de 30**.
- **PR #14:** baselines do Haiku e limites do golden de roteamento apertados (piso de 85%, tolerância de 10 p.p.).
  Evidências em `evidencias/runner-haiku/`.

## 6. O que fica para o grupo decidir

- Se o golden de dúvidas deve ganhar casos de `outros` (hoje ele não tem essa classe, e o agente do grupo tem).
- Qual LLM vai para produção. No Azure da Aula 6 o agente rodou com o provedor `simulado`; o gate mede o `qwen2.5:3b`.
- Se vale trazer mais peças do grafo (orquestrador e especialistas) quando houver um LLM pago no CI, e com que orçamento
  por PR.

## 7. Evidências (`evidencias/`)

| Arquivo | O que prova |
| --- | --- |
| `roteador-template.txt`, `roteador-quantum.txt`, `roteador-quantum-sem-exemplos.txt`, `roteador-quantum-ajustado.txt` | As quatro versões do prompt comparadas |
| `roteamento_180.py`, `roteamento-180-*.json` | A comparação nas 180 reclamações, caso a caso |
| `eval-quantum*.json`, `gate-eval-quantum*.txt` | As 36 dúvidas com cada versão do roteador |
| `final-roteamento.json`, `gate-final-roteamento.txt`, `final-politicas.json`, `gate-final-politicas.txt` | Os dois goldens com a configuração do PR, pelo promptfoo, como o CI roda |
| `ci-pr11-run-*.log` | Os logs completos das duas execuções do PR #11 |
| `runner/<run>/resultado-*.json`, `runner/ruido-3-execucoes-runner.txt` | Os resultados das três execuções no runner e a tabela de ruído |
