# Aula 5 — MLflow: Model Registry e Prompt Registry

Registro da execução da Aula 5 nesta cópia em 22/11/2026, sem dupla. Roteiro: `roteiros/aula-05.md`.

**Resultado:** as seções 2 a 4 (registro, gate, rollback) e o bônus da seção 5 (Prompt Registry) rodaram como o roteiro
descreve, com o **MLflow local** (opção B, gratuita). Dois problemas no material: o rollback não atualiza o `@anterior` e a
linhagem do prompt aponta para um commit que não contém o texto registrado (seção 4).

## Linha do tempo

| # | O que foi feito | Por quê |
| --- | --- | --- |
| 1 | `.venv` com Python 3.12 pelo `uv`, com `requirements.txt` e `mlops/requirements.txt` | Mesma versão do CI e do Codespace. Com o Python 3.12 do `uv`, o `scipy` carrega no macOS: o erro do `dyld` da Aula 2 era do Python do sistema |
| 2 | Opção B: MLflow em `mlflow.db` (sem `MLFLOW_TRACKING_URI`) | Não gasta crédito do Learner Lab; o roteiro aceita as duas opções |
| 3 | Seções 2, 3 e 4 na ordem do roteiro | Ver o ciclo candidato → gate → produção → rollback |
| 4 | Conferência dos aliases, das tags de linhagem e do `load_model` pelo alias | Provar que o registry guarda o que o roteiro promete, além do que os scripts imprimem |
| 5 | Bônus: Prompt Registry, com uma versão 2 só no `@staging` | O mesmo desenho de aliases, agora para prompt |

## 1. Model Registry (seções 2 a 4)

```text
$ python mlops/registrar_modelo.py
Run 55b271a8… · F1 macro 0.8295 · {'positiva': 0.8835, 'negativa': 0.8125, 'neutra': 0.7925}
Registrado: classificador-avaliacoes versão 1 → alias @candidato
$ python mlops/promover.py
✅ Versão 1 promovida a @producao

$ python mlops/registrar_modelo.py --dados classificador/dados/lote-novo.csv
Run 597b3278… · F1 macro 0.731 · {'positiva': 0.8291, 'negativa': 0.7805, 'neutra': 0.5833}
Registrado: classificador-avaliacoes versão 2 → alias @candidato
$ python mlops/promover.py
❌ Versão 2 NÃO promovida:
   - F1 macro 0.731 < 0.8
   - F1 da classe 'neutra' 0.5833 < 0.7
   - piora de 0.0985 no F1 macro em relação à produção (0.8295)

$ python mlops/registrar_modelo.py --C 8 && python mlops/promover.py
Run ce3bc90f… · F1 macro 0.8331 · {'positiva': 0.8845, 'negativa': 0.8148, 'neutra': 0.8}
✅ Versão 3 promovida a @producao (@anterior = 1)
$ python mlops/promover.py --rollback
↩️  Rollback: @producao agora é a versão 1 (era 3)
```

- **O gate é o mesmo da Aula 2** (`model_gate.avaliar`), com uma diferença: a referência agora é a versão em `@producao`
  no registry (0,8295), e não o `producao.json` (0,82). Por isso a "piora" do lote ruim é 0,0985 aqui e 0,0890 na Aula 2.
- **O modelo carrega pelo alias:** `mlflow.sklearn.load_model("models:/classificador-avaliacoes@producao")` classificou
  três frases de teste como `positiva`, `negativa` e `neutra`.
- **Quem aprovou fica registrado:** as versões promovidas têm as tags `aprovado_por` e `promovido_em`; a versão 2
  (reprovada) não tem nenhuma.

### Linhagem: dado o `dados_sha256`, quais dados geraram o modelo?

| Versão | `dados_arquivo` | `dados_sha256` | `git_commit` |
| --- | --- | --- | --- |
| 1 | `avaliacoes.csv` | `bc2d526021ed` | `334dc7a` |
| 2 | `lote-novo.csv` | `d23de78585e5` | `334dc7a` |
| 3 | `avaliacoes.csv` | `bc2d526021ed` | `334dc7a` |

Basta calcular o SHA-256 (12 primeiros caracteres) de cada arquivo de dados e comparar: `avaliacoes.csv` dá
`bc2d526021ed`, `lote-novo.csv` dá `d23de78585e5`. O nome do arquivo sozinho não basta, porque o arquivo pode mudar com o
mesmo nome. O hash é o que prova que os dados são os mesmos.

## 2. Prompt Registry (bônus da seção 5)

```text
$ python mlops/registrar_prompts.py -m "versão inicial"
quantum-roteador versão 1 · commit 334dc7a
quantum-especialista versão 1 · commit 334dc7a
$ python mlops/registrar_prompts.py --alias producao --versao 1
@producao → versão 1 em roteador, especialista
$ PROMPT_FONTE=mlflow PROMPT_ALIAS=producao LLM_PROVEDOR=simulado python agente/atendimento.py "Comprei um perfume que parece falsificado"
{ "categoria": "falsificado", "documento": "falsificado.md", "resposta": "O cliente que suspeitar … 30 dias …", … }
```

Depois, como o roteiro pede: acrescentei uma linha ao `especialista.txt` ("Sempre termine oferecendo o protocolo do
atendimento."), registrei a versão 2, movi **só** o `@staging` e desfiz a edição no Git:

```text
@staging → versão 2 em roteador, especialista
producao → última linha: Chamado do cliente: {{chamado}}
staging  → última linha: Sempre termine oferecendo o protocolo do atendimento.
```

O agente com `PROMPT_ALIAS=staging` recebe o texto novo e o de `producao` continua no antigo, sem deploy de código.

**Por que conferi o texto e não a resposta:** com `LLM_PROVEDOR=simulado` a resposta sai de regras por palavra-chave e
**não depende do prompt**. A saída do roteiro prova só que o agente rodou, não que o prompt veio do registry.

## 3. Perguntas da aula

- **O Git ou o registry é a fonte da verdade do texto?** O Git: é lá que o PR é revisado. O registry guarda versão,
  linhagem e métricas. O problema 2 abaixo mostra por quê: o registry aceita qualquer texto, inclusive um que nunca
  passou por PR.
- **Quem pode mover o alias `producao`?** No MLflow local, qualquer um com acesso ao arquivo `mlflow.db`. No servidor do
  EC2, qualquer um que alcance a porta 5000: o `servidor-mlflow-ec2.sh` não tem autenticação. O equivalente ao
  `CODEOWNERS` seria só o CI mover o `@producao`, depois do gate.
- **O rollback do registry basta?** Não. Ele só troca o ponteiro. Um serviço que já carregou o modelo continua com o
  antigo até recarregar. O Lambda da Aula 4 serve a imagem que foi construída e não lê o registry. E o
  `PROMPT_VERSAO` do GitOps (Aula 3) é outra fonte, que também precisa voltar.

## 4. Problemas encontrados nos materiais (com evidência)

1. **O rollback não atualiza o `@anterior`.** Depois do rollback, `@producao` e `@anterior` apontam para a versão 1, e
   a v3 continua como `@candidato`. Consequências:
   - um segundo `--rollback` imprime `↩️ Rollback: @producao agora é a versão 1 (era 1)`: diz que fez e não fez nada;
   - o próximo `promover.py` promove a v3 de novo, porque ela passa no gate, e nada registra que ela já foi
     revertida.

   *Sugestão:* no rollback, mover o `@candidato` para fora da versão revertida (ou marcá-la com uma tag
   `revertida_em`) e recusar quando `@anterior == @producao`.
2. **A linhagem do prompt pode apontar para o commit errado.** O `registrar_prompts.py` lê o arquivo do disco e grava o
   `git_commit` do `HEAD`. A versão 2 acima foi registrada com `commit 334dc7a`, mas o texto dela nunca foi commitado.
   *Sugestão:* recusar o registro se `git status --porcelain agente/prompts` não estiver vazio, ou rodar o registro só no
   CI, depois do merge.
3. **O registro sempre cria versão nova dos dois prompts**, mesmo quando só um mudou (`quantum-roteador` v2 é idêntico à
   v1). Isso confunde a pergunta "qual versão mudou?".
4. **A resposta do agente não diz qual versão do prompt atendeu.** Com `PROMPT_FONTE=mlflow`, o campo `prompt_versao`
   continua `"arquivo"` (vem da variável `PROMPT_VERSAO` do GitOps). É o mesmo papel do `"versao"` na resposta do
   classificador (Aula 2), mas o agente não o cumpre.

## 5. O que não foi testado

- **Opção A (MLflow no EC2 do AWS Academy):** não gastei crédito com ela. Ela não muda nada nos scripts, só a
  `MLFLOW_TRACKING_URI`.
- **A interface do MLflow** (`mlflow server …`): conferi os runs e as tags pela API (`MlflowClient`), que é o que a
  interface mostra.

## 6. Cuidados daqui para a frente

- O `mlflow.db` e a pasta `mlruns/` ficam na raiz e estão no `.gitignore`. O estado final é `@producao = 1`,
  `@anterior = 1` e `@candidato = 3`; prompts com `@producao = 1` e `@staging = 2`.
- Para recomeçar do zero: `rm -rf mlflow.db mlruns`.

## 7. Evidências (`evidencias/`)

| Arquivo | O que prova |
| --- | --- |
| `01-model-registry.log` | As seções 2 a 4: registro, gate, promoção e rollback |
| `02-prompt-registry.log`, `03-prompt-staging-v2.log` | O Prompt Registry e a versão 2 só no `@staging` |
| `04-estado-do-registry.txt` | Os aliases finais, as tags de linhagem, os SHA-256 dos dados e o problema do `@anterior` |
