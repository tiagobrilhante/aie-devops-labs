# Aula 6 — Capstone: o agent gate

Registro da execução da Aula 6 nesta cópia em 22/11/2026, sem dupla. Roteiro: `roteiros/aula-06.md`.

**Resultado:** todas as seções rodaram. O gate local, a regra da categoria que piora, o gate no CI, o override e o juiz
de fidelidade funcionaram. O deploy foi para o **Azure Web Apps**, a alternativa do roteiro, porque o Learner Lab da
turma foi encerrado (ver a Aula 4): o gate passou no runner, o agente subiu e respondeu, e a infra foi **apagada** em
seguida para não gastar crédito. Achados que mudam como ler o gate: seções 2 e 3 e problemas 1 a 3. Um achado muda o
que o deploy prova: o gate testa um LLM e a produção roda outro (problema 7).

## Linha do tempo

| # | O que foi feito | Por quê |
| --- | --- | --- |
| 1 | Ollama nativo no Mac (já instalado) + `ollama pull qwen2.5:3b` (46 s) | Mesmo modelo do CI; no Apple Silicon ele roda na GPU (Metal) |
| 2 | promptfoo 0.123.1 pelo `npx`, com `PROMPTFOO_PYTHON` apontando para o `.venv` 3.12 | O provedor `provedor_promptfoo.py` precisa do Python com `openai` e `pyyaml` |
| 3 | Eval de base + `agent_gate.py` | Seção 2 |
| 4 | `--salvar-baseline` e quatro variantes do `roteador.txt` (A a D), sempre com `--no-cache` | Seção 3: a regra "categoria piora mesmo que a média melhore" |
| 5 | Três execuções do prompt original | Medir o ruído real antes de concluir qualquer coisa sobre a tolerância |
| 6 | PR #7: o especialista para de citar prazos e valores → gate no runner → rótulo de override | Seção 4 |
| 7 | Juiz de fidelidade com `qwen2.5:3b` e com `qwen2.5:32b` (local) | Seção 5: o roteiro diz que o juiz de 3B é fraco; conferi se um maior resolve |
| 8 | `baseline.json` e `roteador.txt` restaurados (`git checkout`) | Os experimentos não podiam ficar na `main` |
| 9 | Tentativa de abrir o Learner Lab: *"This course has ended"* | O deploy padrão é no Lambda |
| 10 | `brew install azure-cli`; `az login` (feito por você) na assinatura *Azure for Students* | Alternativa do roteiro |
| 11 | `azure/criar-webapp.sh`; secret e variável cadastrados à mão | O script não conseguiu ligar o GitHub (problema 8) |
| 12 | `gh workflow run "Aula 6 · Deploy do agente (Azure Web Apps)"` e chamadas à URL | Seção 6 |
| 13 | `az group delete` e conferência de que nada desta sessão ficou | Não gastar crédito (pedido seu) |

## 1. Seção 2 — o gate

O eval levou **30 s** no Mac (36 casos, `maxConcurrency: 2`), contra ~13 min no runner do GitHub (2 vCPU, só CPU).

```text
| Categoria | Roteamento | Recuperação | Resposta |
| artigo_proibido | 67% | 67% | 67% |
| devolucao_ressarcimento | 100% | 100% | 100% (+33%) |
| divergente_defeito | 83% | 83% | 100% |
| entrega | 83% | 83% | 83% (-17%) |
| falsificado | 100% | 100% | 83% (-17%) |
| fraude_vendedor | 83% | 83% | 83% |
| **média** | **86%** | **86%** | **86%** |
**✅ Aprovado**
```

Os deltas são em relação ao `baseline.json` do template, medido no runner.

## 2. Seção 3 — a categoria que piora

Baseline fixada com `--salvar-baseline` sobre o eval de base. Depois, quatro variantes do roteador:

| Variante | O que mudou no `roteador.txt` | `fraude_vendedor` (roteamento) | Média (roteamento) | Gate |
| --- | --- | --- | --- | --- |
| A (a do roteiro) | apaga a linha de `fraude_vendedor`; melhora `artigo_proibido` | 83% → **0%** | 86% → 78% | ❌ piso **e** regressão nas 3 camadas |
| B | fraude só com "Pix ou transferência"; melhora entrega, divergente e artigo | 83% → 67% | 86% → **92%** | ✅ |
| C | B + "caixa vazia" em divergente, "rastreio que não existe" em entrega | 83% → 67% | 86% → **92%** | ✅ |
| D | C + fraude só "quando o cliente AINDA NÃO pagou"; devolução fica com "dinheiro já pago" | 83% → **50%** | 86% → **92%** | ✅ |

**O que isso mostra:**

- **A variante do roteiro reprova, mas a média também cai** (78%). Ela não mostra "a média igual ou melhor" que o
  enunciado pede: apagar a categoria inteira derruba tanto que nenhuma melhora compensa.
- **A variante D é o caso do enunciado, e o gate aprova.** `fraude_vendedor` perde 2 de 6 casos (−33 p.p.) e a média
  **sobe** para 92%. O gate deixa passar porque a tolerância é 0,34 e 2 casos valem 0,333.
- **Com 6 casos por categoria, a regra 2 (regressão) quase nunca dispara sozinha.** Ela exige perder 3 casos ou mais.
  Saindo de 5/6, cair 3 dá 2/6 = 33%, que já fura o piso de 50% (regra 1). A regra 2 só dispara sem a regra 1 quando
  a categoria estava em 100% e cai para exatamente 50%.

**O ruído é real ou não?** A tolerância foi calibrada no runner, onde "categorias oscilaram até 2 casos entre execuções"
(comentário do `limites.yaml`). Aqui, rodei o prompt original 3 vezes, sem cache: **0 casos diferentes**, na categoria e
na nota de resposta. O PR #7 (seção 3) mostra o outro lado: o mesmo prompt deu resposta média de 72% no Mac e 64% no
runner. O ruído depende do hardware, e a tolerância vale para o runner. Neste Mac, a queda da variante D é uma
regressão de verdade, que o gate aprovou.

## 3. Seção 4 — o gate no CI e o override (PR #7)

Mudança no `especialista.txt`: "resuma com as suas palavras: não repita números, prazos nem valores".

| Onde | Resposta (média) | Veredito | Tempo |
| --- | --- | --- | --- |
| Mac (Metal) | 72% | ❌ `artigo_proibido/resposta: 33% abaixo do piso de 50%` | 30 s |
| Runner, run `45031209778` | 64% | ❌ o mesmo motivo | 8 min 47 s (job do gate) |
| Runner, run `45032133520`, depois do rótulo | 64% | ⚠️ "Reprovado, mas liberado por OVERRIDE: rótulo override-agent-gate no PR #7, aplicado com tiagobrilhante como autor da execução" | 9 min 26 s |

O rótulo `override-agent-gate` não existia na cópia: criei com `gh label create`. O evento `labeled` disparou o workflow
de novo, como o roteiro diz. O PR foi fechado sem merge.

**Vale notar:** a resposta média caiu de 86% para 64% (−22 p.p.) e só **uma** categoria furou o piso. Com outro
sorteio do ruído, o PR passaria sem nenhum alerta.

## 4. Seção 5 — o juiz de fidelidade

| Juiz | Tempo | Resultado | Casos reprovados |
| --- | --- | --- | --- |
| `qwen2.5:3b` (padrão) | 54 s | ✅ (só informa) | 8 (um com nota 0,5) |
| `qwen2.5:32b` (local, via `LLM_JUIZ_MODELO`) | 6 min 47 s | ✅ (só informa) | 7 |

As respostas do agente saíram idênticas nas duas execuções, então os juízes julgaram o **mesmo texto**:

- **A contradição que importa:** no Pix, o agente diz "o valor será bloqueado e devolvido ao comprador em até 5 dias
  úteis", e a política diz que **não reembolsa** pagamento fora da plataforma. O 32b reprovou. O 3b deu 0,5 ("não
  contradiz… mas não menciona").
- **Alarmes falsos absurdos do 3b, que o 32b não deu:** papagaio ("'animais silvestres' não corresponde a
  'papagaio'"), bolsa ("'não é necessário devolver' contradiz 'não precisa ser devolvido'") e B.O. (a resposta cita o
  protocolo).
- **Os dois desobedecem a rubrica num ponto:** ela diz que a resposta "pode omitir o fato". Mesmo assim, os dois
  reprovam respostas que só o omitem (perícia, denúncia de anúncio), e o 32b reprova também uma paráfrase ("abatimento
  no valor pago" × "abatimento proporcional").
- **Os dois pegam o caso do rastreio parado:** a resposta oferece o cupom de R$ 30 (atraso) em vez do reenvio
  (extravio).

**Conclusão:** o modelo maior acaba com os alarmes absurdos e pega a contradição real inteira, mas ainda reprova
omissões. Para `JUIZ_BLOQUEIA=true`, a rubrica precisa de um exemplo de omissão aprovada, ou o piso deve contar só
contradições.

## 5. Seção 6 — o deploy (Azure Web Apps)

1. **AWS fora do ar para esta turma.** O Learner Lab respondeu *"This course has ended and can no longer be accessed
   through your LMS"* (prints em `../aula4/evidencias/`). Por isso, o caminho alternativo do roteiro: Azure Web Apps.
2. **Criação do Web App** (`azure/criar-webapp.sh`, 58 s): o script leu a política da sua assinatura (regiões
   permitidas: `brazilsouth`, `canadacentral`, `chilecentral`, `eastus`, `northcentralus`), conseguiu o plano B1 na
   primeira (`brazilsouth`) e criou o app `agente-quantum-23771` (Python 3.12, `LLM_PROVEDOR=simulado`).
3. **GitHub:** o script não cadastrou nada (problema 8). Cadastrei o secret `AZURE_WEBAPP_PUBLISH_PROFILE` (direto do
   `az` para o `gh`, sem passar pela tela) e a variável `AZURE_WEBAPP_NAME`.
4. **Workflow** (run `45036817174`): agent gate no runner **aprovado** (11 min 05 s; média 86% / 86% / 81%) → deploy
   (3 min 39 s, `Successfully deployed web package to App Service`) → *smoke test* ok. O publish profile aparece mascarado
   (`***`) no log.
5. **O agente no ar:**

| Chamada | Resposta |
| --- | --- |
| `GET /` | 200 · `{"status":"ok","prompt_versao":"arquivo","modelo":"simulado:regras-v1"}` |
| "Meu pedido está atrasado há 6 dias úteis" | `entrega` · "… cancelamento com reembolso integral ou … cupom de R$ 30 …" |
| "O vendedor me pediu pra pagar por Pix direto pra ele e sumiu" | `fraude_vendedor` · "A Quantum não reembolsa pagamentos feitos fora da plataforma, mas …" |
| "Comprei um perfume que parece falsificado" | `falsificado` · "… denúncia em até 30 dias …" |
| "Tem gente vendendo filhote de papagaio no site, isso pode?" | `artigo_proibido` · "… analisa em até 48 horas …" |
| `{"text": "campo errado"}` | 422 · `Field required: texto` |

   Cada chamada levou de 0,4 a 0,6 s, de São Paulo para `brazilsouth`.
6. **Limpeza:** `az group delete -n rg-aie-capstone-brazilsouth --yes` (1 min 18 s). Depois disso, nenhum grupo `rg-aie-*`
   e nenhum recurso desta sessão. A URL não responde mais. Ficaram dois recursos **anteriores** (de 01/07/2026), que não
   toquei: a storage `cloudfiapi1` (grupo `FIAP`) e o `NetworkWatcher_brazilsouth` (sem custo).

## 6. Problemas encontrados nos materiais (com evidência)

1. **A variante sugerida na seção 3 não demonstra "média igual ou melhor".** Apagar a linha de `fraude_vendedor`
   derruba a média de 86% para 78%. *Sugestão:* propor uma piora parcial e citar a tabela acima, que mostra o gate
   aprovando uma queda de 2 casos com a média em alta.
2. **Com 6 casos por categoria, a regra de regressão é quase redundante com o piso** (seção 2). Isso confirma o
   "Dataset pequeno = gate frouxo" do `limites.yaml`: a regra só ganha força com mais casos por categoria.
3. **O override não tem justificativa e continua valendo.** O workflow monta um texto fixo (PR + autor) em vez da
   justificativa que o `agent_gate.py` espera. E o rótulo é avaliado em todo evento: depois de aplicado, **cada commit
   novo** no PR passa liberado, mesmo que piore mais. *Sugestão:* ler a justificativa de um comentário do PR e
   remover o rótulo a cada `synchronize`.
4. **`--salvar-baseline` grava a baseline mesmo quando o gate reprova** (`agent_gate.py`: o `write_text` vem antes do
   `sys.exit(1)`). Rodado na `main` depois de um deploy ruim, ele fixa a piora como nova referência.
5. **O rótulo `override-agent-gate` não vem na cópia.** O *Use this template* não copia rótulos; o roteiro não diz para
   criar.
6. **O juiz desobedece a parte "pode omitir" da rubrica** (seção 4), com os dois modelos.
7. **O gate aprova um LLM e a produção roda outro.** O gate do deploy avaliou o `qwen2.5:3b` (Ollama no runner); o
   agente publicado responde com `simulado:regras-v1`, porque o Web App não roda Ollama e nenhum Foundry foi
   configurado. É o mesmo provedor que, segundo o README, *reprova* no gate. O deploy prova a **esteira** (gate →
   pacote → App Service), não que o agente em produção passou no gate. *Sugestão:* o workflow deveria rodar o gate com o
   **mesmo** provedor e modelo que vão para produção, ou recusar o deploy quando forem diferentes.
8. **O `criar-webapp.sh` falha em silêncio ao ligar o GitHub quando há mais de um remote.** Com o remote `template`
   (que o próprio README manda adicionar para atualizar a cópia), o `gh secret set` responde *"multiple remotes
   detected"*. A cadeia `&&` não imprime erro, e o script termina com "✅ Web App criado". O deploy falharia depois por
   falta do secret. *Sugestão:* passar `-R "$(gh repo view --json nameWithOwner -q .nameWithOwner)"` e avisar quando o
   `gh` falhar.

## 7. O que não foi testado

- **O deploy no Lambda** (o caminho padrão): o Learner Lab da turma foi encerrado.
- **Um LLM real em produção** (Foundry / Azure OpenAI): o agente no ar usou o provedor `simulado`.
- **O juiz no GitHub** (`workflow_dispatch` com `com_juiz`): só local.

## 8. Cuidados daqui para a frente

- **A infra do Azure foi apagada.** Para subir de novo (por exemplo, para a apresentação do capstone): `az login`,
  `azure/criar-webapp.sh` (cadastre o secret com `-R` se tiver o remote `template`), `gh workflow run "Aula 6 · Deploy
  do agente (Azure Web Apps)"`, e **apague de novo** ao terminar: `az group delete -n rg-aie-capstone-brazilsouth --yes`.
- O secret `AZURE_WEBAPP_PUBLISH_PROFILE` e a variável `AZURE_WEBAPP_NAME` ficaram no GitHub apontando para o app
  apagado. Rodar o workflow agora falharia no deploy. São substituídos quando você recriar o app.
- O `baseline.json` versionado continua o do template, medido no runner. Não versione uma baseline medida no Mac: o
  ruído é outro e o CI compararia hardwares diferentes.

## 9. Evidências (`evidencias/`)

| Arquivo | O que prova |
| --- | --- |
| `evals/eval-base*.json`, `ruido-3-execucoes.txt` | Eval de base e as 3 execuções idênticas (0 casos diferentes) |
| `gate-base.txt` | O gate do eval de base, contra o `baseline.json` do template |
| `baseline-local.json`, `roteador-variante-{a,b,c,d}.txt`, `evals/eval-regressao*.json`, `gate-variante-{a,b,c,d}.txt` | Seção 2: as variantes contra a baseline local (A/B reconstruídas com as mesmas trocas) |
| `evals/eval-especialista-ruim.json`, `gate-especialista-ruim-local.txt` | O prompt do PR #7 reprovando no Mac |
| `pr7-ci-gate-reprovado.log`, `pr7-ci-gate-override.log` | O PR #7 no runner: reprovado e depois liberado pelo override |
| `evals/juiz-3b.json`, `evals/juiz-32b.json`, `juiz-*-resumo.txt`, `juizes-caso-a-caso.md` | Seção 4: os dois juízes, caso a caso |
| `baseline-do-template.json` | O `baseline.json` original (restaurado depois dos experimentos) |
| `azure-criar-webapp.log` | A criação do Web App e o erro *"multiple remotes detected"* |
| `azure-deploy-run-45036817174.log` | O workflow de deploy: gate, pacote, App Service, smoke test |
| `azure-agente-no-ar.txt` | As chamadas ao agente publicado |
| `azure-recursos-antes-de-apagar.txt`, `azure-limpeza.txt` | Os recursos criados (B1) e a limpeza |
