# Aula 3 — GitOps com Argo CD: o que foi feito e por quê

Registro da execução da Aula 3 nesta cópia em 22/11/2026, sem dupla. Roteiro: `roteiros/aula-03.md`, na versão
atualizada do template (PR #4, que traz o "passo 0" e a pergunta do agente de SRE).

**Resultado:** todos os passos e os dois bônus rodaram. A promoção pelo Git levou **16 s** do merge ao deploy, e o
rollback por `git revert`, **20 s**. O bônus do `selfHeal` **não funciona como o roteiro descreve**: o merge não chega ao
cluster (problema 1). Achei também uma pegadinha que faz parecer que funciona (problema 2).

## Linha do tempo

| # | O que foi feito | Por quê |
| --- | --- | --- |
| 1 | PR #4: `roteiros/aula-03.md` e `aula-04.md` trazidos do template | O template mudou esses roteiros depois de 14/10. Só esses dois arquivos: `aula-01-codeowners.md` foi reescrito por você no #2 |
| 2 | `brew install kind` (v0.33.0, a mesma do `.devcontainer`) | O Mac já tinha Docker e `kubectl`; faltava o `kind` |
| 3 | Passo 0: `gitops/scripts/subir-cluster.sh` no Mac, em vez do Codespace | O script roda em qualquer máquina com Docker e lê o `origin` (esta cópia, pública) |
| 4 | Passo 2: drift nos dois ambientes ao mesmo tempo | Ver lado a lado `selfHeal: false` (produção) e `true` (staging) |
| 5 | Bônus: PR #6 com `latest` e `OPENAI_API_KEY=sk-123`, fechado sem merge | Ver o check do PR barrar antes do merge |
| 6 | Passo 1: PR #5 (`v11` → `v12` em produção), merge com *bypass* | Promover pelo Git: o merge é o deploy |
| 7 | Bônus: PR #8 (`selfHeal: true` em produção), merge, drift de novo e um teste de controle | Ver se o merge muda a política no cluster |
| 8 | Bônus: PR #9 (`git revert` do #5), merge | Medir o rollback pelo Git |

O auto mode do Claude Code bloqueou o `gh pr merge --admin` (o *bypass* do ruleset). Os merges dos PRs #4, #5, #8 e #9
foram feitos por você.

## 1. Passo 0 — o cluster

`subir-cluster.sh` levou **3 min 08 s** (kind + Argo CD v3.5.3 + os dois `Application`). O roteiro diz ~3 min.

```text
$ gitops/scripts/consultar.sh
agente-staging   ambiente=staging modelo=openai/gpt-4.1-mini prompt=v12 temperatura=0.2 rag=politicas-2026-09
agente-producao  ambiente=producao modelo=openai/gpt-4.1-mini prompt=v11 temperatura=0.2 rag=politicas-2026-09

APP               SYNC     SAÚDE     REVISÃO
agente-producao   Synced   Healthy   334dc7a6e07e572ab688029b20f53539fde7155f
agente-staging    Synced   Healthy   334dc7a6e07e572ab688029b20f53539fde7155f
```

Critério do passo 0 atendido: staging em `v12`, produção em `v11`, os dois *Synced*. Produção tem 3 réplicas
(`escala.patch.yaml`); staging, 1.

## 2. Passo 1 — promover pelo Git (PR #5)

- Mudança: `PROMPT_VERSAO=v11` → `v12` em `gitops/overlays/producao/inference-config.env`.
- *Aula 3 · Checks do PR*: **passou** (12 s), com o `diff` de cada ambiente no resumo da execução.
- **Merge às 14:39:56; o Argo CD fez o deploy em produção às 14:40:12: 16 s.** O roteiro promete menos de 1 min, com o
  *polling* de 30 s que o `subir-cluster.sh` configura.

```text
agente-producao  ambiente=producao … prompt=v12 …
agente-producao   Synced   Healthy   a8f7524…
```

**Efeito colateral:** o drift de 5 réplicas que estava em produção (passo 2) **sumiu** nesse deploy, e voltaram as 3.
Mesmo com `selfHeal: false`, o sync de uma revisão nova reaplica o Git inteiro. Na prática, uma mudança manual em
produção só dura até o próximo deploy.

## 3. Passo 2 — drift

```text
$ kubectl -n agente-producao scale deploy/agente-suporte --replicas=5
$ kubectl -n agente-staging  scale deploy/agente-suporte --replicas=4
t=0s produção: OutOfSync réplicas=5 | staging: OutOfSync réplicas=4
t=3s produção: OutOfSync réplicas=5 | staging: Synced réplicas=1
```

- **O drift é detectado na hora, não a cada 30 s.** O Argo CD observa o cluster continuamente. O *polling* de 30 s é
  só para olhar o **Git**.
- **Staging se curou em menos de 3 s** (`selfHeal: true`). O evento registra
  `Partial sync operation to 334dc7a… succeeded`: ele reaplicou só o `Deployment`.
- **Produção fica `OutOfSync` com 5 réplicas** (`selfHeal: false`) e o Argo CD aponta exatamente o recurso:
  `Deployment/agente-suporte → OutOfSync`. Ninguém desfaz sozinho; alguém decide.

### A pergunta do agente de SRE

*"Se quem rodou o `kubectl` fosse um agente, onde ele pode agir direto e onde só pode abrir um PR?"* Proposta:

- **Direto, só em staging:** lá o `selfHeal` desfaz em segundos qualquer coisa que ele faça. O estrago se limita a
  alguns segundos.
- **Em produção, só por PR:** ele abre o PR no `gitops/overlays/producao/`, que tem *code owner* e o check de política.
  O agente não recebe permissão de escrita no namespace de produção (RBAC só de leitura). É a mesma regra do
  `CODEOWNERS`: quem muda produção sem revisão? Ninguém, nem um agente.

Linha para o chat: *decidimos que o agente só age direto em staging e, em produção, só abre PR; quebrou o drift de
produção, que só alerta e precisa de gente.*

## 4. Bônus — `selfHeal: true` em produção (PR #8)

| Etapa | `selfHeal` no Git | `selfHeal` no cluster | Drift de 5 réplicas em produção |
| --- | --- | --- | --- |
| Depois do merge do #8 | `true` | **`false`** | voltou a 3 depois de ~14 s (ver o problema 2: **não** é `selfHeal`) |
| Controle: `selfHeal=false`, revisão já sincronizada | `true` | `false` | **continua `OutOfSync` com 5 réplicas** depois de 31 s |
| Depois de reaplicar os `Application` (`kubectl apply`) | `true` | `true` | volta a 3 em menos de 2 s, sem nem aparecer `OutOfSync` |

Para reaplicar, usei o mesmo laço do `subir-cluster.sh`:
`for app in gitops/apps/*.yaml; do sed "s#REPO_URL#$(git remote get-url origin)#" "$app" | kubectl apply -f -; done`.

**Qual política escolher para produção?** `selfHeal: true`. O argumento do `false` ("alguém decide") não se sustenta:
a mudança manual é apagada de qualquer jeito no próximo deploy (seção 2), então ela só cria uma janela em que o
cluster mente sobre o Git. O preço do `true`: uma correção de emergência feita à mão (por exemplo, escalar durante um
incidente) é desfeita em segundos. Por isso ela também precisa passar pelo Git, num PR rápido com *bypass* registrado.

## 5. Bônus — quebrar a política (PR #6)

```text
❌ Políticas violadas:
   - [staging] PROMPT_VERSAO precisa de versão explícita (está 'latest')
   - [staging] 'OPENAI_API_KEY' parece segredo em texto claro — use um Secret externo
```

O check do PR reprovou com os **dois** motivos, igual ao teste local. Fiz a mudança no overlay de **staging** de
propósito: lá o `selfHeal: true` aplicaria o `latest` logo depois do merge, então o check precisa vir **antes**. O PR
foi fechado sem merge.

**Atenção:** a chave `sk-123` é falsa, mas ficou no histórico da branch apagada e no PR #6 (fechado), que são
públicos. O GitGuardian não acusou nada (o formato não parece chave real). Com uma chave real, apagar a branch não
basta: o certo é revogar a chave.

## 6. Bônus — rollback com `git revert` (PR #9)

**Merge às 14:48:22; o Argo CD fez o deploy em produção às 14:48:42: 20 s.** Produção voltou a responder `prompt=v11`.
O rollback custa o mesmo que a promoção, porque também é um commit. O que o atrasa é a revisão do PR, não o Argo CD:
sem o *bypass*, o rollback espera alguém aprovar.

## 7. Perguntas dos critérios da aula

- **Onde está declarado qual modelo e prompt rodam em cada ambiente?** Em `gitops/base/agente-suporte/inference-config.env`
  (o comum) e nos `inference-config.env` de cada overlay (só o que difere). O `diff` dos dois overlays responde "o que
  ainda não foi promovido".
- **Onde fica a chave do LLM sem estar em texto claro?** Num `Secret` externo (Sealed Secrets, External Secrets com o
  Secrets Manager da AWS). O check do PR barra a chave no `ConfigMap`, mas o repositório não traz o caminho certo:
  falta um exemplo de `Secret`.
- **Quem muda produção sem revisão?** Pelo Git, ninguém: `CODEOWNERS` em `/gitops/overlays/producao/` e o ruleset com
  1 aprovação. Fora dele: quem tem `kubectl` no cluster (o drift do passo 2) e quem tem *bypass* no ruleset (o admin,
  que é o caso solo).

## 8. Problemas encontrados nos materiais (com evidência)

1. **O bônus do `selfHeal` não funciona como descrito.** Os `Application` são aplicados **uma vez** pelo
   `subir-cluster.sh` (`kubectl apply`), e nenhum `Application` observa `gitops/apps/`: o cluster só tem
   `agente-producao` e `agente-staging`, que observam os overlays. Depois do merge do #8, o Git dizia `true` e o
   cluster continuava `false` (seção 4). *Sugestão:* dizer no roteiro para rodar o `subir-cluster.sh` de novo depois do
   merge, ou criar um *app of apps* que observe `gitops/apps/`.
2. **Pegadinha: logo depois de um commit qualquer, o primeiro drift "se cura" mesmo com `selfHeal: false`.** O commit
   do #8 não mexeu nos overlays, então o Argo CD não fez sync da revisão nova. Quando o drift deixou a app
   `OutOfSync`, o *auto-sync* viu uma revisão nunca sincronizada e sincronizou uma vez (`Initiated automated sync to
   'd511d5e…'`). Quem testar o `selfHeal` assim conclui, errado, que o merge funcionou. O teste de controle (seção 4)
   separa os dois casos.
3. **Uma mudança manual em produção some no próximo deploy**, com qualquer `selfHeal` (seção 2). O roteiro apresenta
   `selfHeal: false` como "só alerta, alguém decide", mas a decisão tem prazo: o próximo merge.
4. **O merge "solo" depende de *bypass* manual.** Com o ruleset da Aula 1 (1 aprovação), cada promoção e cada rollback
   pelo Git exigem um *bypass* do admin. Isso vale para todas as aulas que promovem por PR (3 e 6).

## 9. O que não foi testado

- O painel web do Argo CD (`port-forward`): usei o `kubectl` e o `consultar.sh`, que mostram o mesmo estado.
- Um Codespace de verdade: o mesmo script rodou no Mac, com Docker.

## 10. Cuidados daqui para a frente

- O cluster `aie` continua rodando no Docker do Mac. Para apagar: `kind delete cluster --name aie`.
- Estado final: staging em `v12`, produção em `v11` (depois do revert), os dois `Synced`, produção com `selfHeal: true`
  no Git **e** no cluster.
- Se recriar o cluster, o `subir-cluster.sh` já aplica o `selfHeal: true` que está na `main`.

## 11. Evidências (`evidencias/`)

| Arquivo | O que prova |
| --- | --- |
| `01-subir-cluster.log` | O passo 0 (3 min 08 s); a senha do Argo CD foi removida |
| `02-drift.log` | O drift nos dois ambientes (staging se cura, produção fica `OutOfSync`) |
| `03-pr6-politica-reprovada.log` | O check do PR #6 reprovando com os dois motivos |
| `04-selfheal-e-controle.log` | O merge do #8 sem efeito no cluster, a pegadinha do auto-sync e o teste de controle |
| `05-pr5-checks-politica.log`, `07-pr9-checks-politica.log` | Os checks dos PRs de promoção e de revert |
| `06-estado-final-e-historico.txt` | O estado final, o histórico de deploys do Argo CD (os 16 s e os 20 s) e os paths observados |
| `../prs.md` | Os PRs #4 a #9, com o estado, quem fez o merge e quando |
