# Aula 5 — desenho de registro e promoção de versões (rascunho para o capstone)

> Rascunho. Entregável da Parte 1 da Aula 5 (Aula 05, p. 20): os quatro itens abaixo. O desenho foi posto à prova na
> Parte 2 com o MLflow local; os problemas que o teste revelou estão em `../aula5/README.md` (seção 4) e mudam o
> desenho.

## 1. Onde o código de treino e o modelo vivem, e quem aprova uma versão

| Artefato | Onde vive | Quem aprova |
| --- | --- | --- |
| Código de treino (`classificador/`) e do agente (`agente/`) | Git, neste repositório | PR revisado por *code owner* (`.github/CODEOWNERS`) com 1 aprovação no ruleset da `main` |
| Texto dos prompts (`agente/prompts/`) | **Git** (fonte da verdade); o Prompt Registry guarda versões, linhagem e métricas | PR com *code owner* (regra explícita para `/agente/prompts/`) |
| Modelo treinado | MLflow Model Registry (`classificador-avaliacoes`); no laboratório, `mlflow.db` local; na AWS, EC2 + S3 | **Só o CI**, depois do gate: o `promover.py` grava `aprovado_por` (o `GITHUB_ACTOR`) e `promovido_em` |
| Qual versão roda em cada ambiente | `gitops/overlays/*/inference-config.env` (`PROMPT_VERSAO`, `MODELO`) | PR no `gitops/overlays/producao/` (*code owner* + check de política) |

**Problema que o grupo precisa resolver:** no modo solo, todo merge usa o *bypass* do admin. Com o grupo no repositório,
a aprovação passa a ser de outra pessoa de verdade. O servidor do MLflow no EC2 (`servidor-mlflow-ec2.sh`) não tem
autenticação: qualquer um que alcance a porta 5000 move o alias `@producao`.

## 2. O que entra no registry a cada versão

| Campo | Hoje (medido na Aula 5) | Falta |
| --- | --- | --- |
| Número da versão | automático (1, 2, 3…) | — |
| Métricas do gate | `f1_macro` e `f1_<classe>` no run | a **versão dos limites** usados no gate (o `model_gate.py` muda com PR) |
| Linhagem de código | tag `git_commit` | **recusar registro com mudança não commitada**: a versão 2 do prompt foi registrada com o commit `334dc7a`, que não contém o texto dela |
| Linhagem de dados | `dados_arquivo`, `dados_sha256`, `validacao_sha256` | — (o hash prova que os dados são os mesmos; o nome do arquivo não) |
| Quem aprovou e quando | `aprovado_por`, `promovido_em` (só nas versões promovidas) | — |
| Para prompts | tags `git_commit` e `gate_<camada>` (médias do agent gate) | métricas **por categoria**, não só a média (a média escondeu a queda de `fraude_vendedor` na Aula 6) |

## 3. Critérios das transições candidato → produção → arquivado

```text
registrar_modelo.py ──► @candidato ──(model gate + canary)──► @producao ──(substituída)──► @anterior ──► sem alias (arquivada)
```

| Transição | Critério objetivo |
| --- | --- |
| → `@candidato` | treinou, registrou com linhagem completa e commit limpo |
| `@candidato` → `@producao` | model gate contra a versão em `@producao`: F1 macro ≥ 0,80, F1 de cada classe ≥ 0,70, queda ≤ 0,02; **e** canary aprovado (Aula 4) |
| `@producao` → `@anterior` | automático quando outra versão é promovida |
| `@anterior` → arquivada | quando uma terceira versão é promovida (perde o alias) |

**Uma versão pode pular direto para produção?** Hoje, **sim**: o `promover.py` promove o `@candidato` logo depois do
gate, sem canary nem shadow. O slide da Aula 05 (p. 18) diz que o candidato só vira produção depois de rodar em
**shadow** sobre tráfego real. Proposta: não pular. A única exceção é a **primeira** versão, que não tem produção para
comparar (o `promover.py` já trata esse caso: compara só com os mínimos absolutos).

## 4. Gatilho de rollback: o quê, em quanto tempo, e onde agir

**O que dispara:** os critérios de rollback do canary (erro, latência, distribuição; ver
[`aula4-propostas-de-rollout.md`](aula4-propostas-de-rollout.md)) ou, em produção, os mesmos sinais com amostra mínima.

**Mudar só o registro não basta.** O teste da Aula 5 mostrou três problemas:

1. **O `--rollback` não atualiza o `@anterior`.** Depois dele, `@producao` e `@anterior` apontam para a mesma versão,
   e um segundo rollback imprime "↩️ Rollback" sem mudar nada.
2. **A versão revertida continua `@candidato`.** O próximo `promover.py` a promove de novo, porque ela passa no gate;
   nada registra que ela já foi revertida.
3. **Quem serve o modelo não lê o registry.** O Lambda das Aulas 2 e 4 serve a imagem construída com o modelo dentro;
   mover o alias não muda o que responde.

**Ordem proposta, da mais rápida para a mais lenta:**

| # | Onde | Como | Tempo medido |
| --- | --- | --- | --- |
| 1 | Rollout (Aula 4) | alias ponderado ou slot volta 100% para a versão estável | segundos (o workflow do canary faz isso sozinho) |
| 2 | GitOps (Aula 3) | `git revert` do PR que mudou `PROMPT_VERSAO` ou `MODELO` | **20 s** do merge até produção (PR #9) |
| 3 | Registry (Aula 5) | `@producao` → versão anterior; marcar a revertida (por exemplo, tag `revertida_em`) e tirá-la de `@candidato` | imediato, mas só tem efeito se o serviço ler o registry |

O registro é a **memória** do rollback (o que estava em produção, quando e por quê), não o mecanismo. *A confirmar com o
enunciado da Aula 6* se o capstone pede o registry do **agente** (prompts) além do modelo.
