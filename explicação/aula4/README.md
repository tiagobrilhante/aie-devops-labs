# Aula 4 — Canary: o que foi feito e por quê

Registro da execução da Aula 4 nesta cópia em 22/11/2026, sem dupla. Roteiro: `roteiros/aula-04.md`, na versão
atualizada do template (PR #4, que dá à candidata manual um `MODELO_VERSAO` próprio).

**Resultado:** **o AWS Academy não está mais disponível.** Ao abrir o Learner Lab, o Vocareum responde *"This course has
ended and can no longer be accessed through your LMS. Please contact your instructor or Vocareum support if you need
access."* O curso `AWS Academy Learner Lab [193436]` aparece no Canvas em **"Matrículas passadas"**. As seções 1 a 3
do roteiro (workflow e passo a passo no Lambda) **não rodaram**.

No lugar delas rodei duas alternativas, sempre com o mesmo `canary_check.py` do workflow:

1. **O plano B gratuito do repositório** (`classificador/deploy/alias_local.py`): o canary saudável foi promovido e o que
   erra 20% foi revertido. Repetindo 50 vezes, porém, **um canary saudável com 10% do tráfego é revertido à toa em ~30%
   das vezes** (seções 1 e 2).
2. **O canary de verdade no Azure** (seção 3): App Service S1 com um *deployment slot* `canary` e roteamento de 10% do
   tráfego, o equivalente ao alias ponderado do Lambda. O canary com falha foi revertido e o saudável, promovido por
   *swap*, mas só **depois de aquecido**: na primeira análise, ele foi revertido por latência (p95 de 2.234 ms contra
   508 ms), por partida a frio. A infra (~52 min, cerca de US$ 0,10) foi apagada no fim.

## Linha do tempo

| # | O que foi feito | Por quê |
| --- | --- | --- |
| 1 | Login no AWS Academy (pelo navegador controlado pelo Claude; o login foi seu) e tentativa de abrir o Learner Lab | A Aula 4 roda no Lambda |
| 2 | Leitura da mensagem do Vocareum e da lista de cursos do Canvas | Entender por que o lab não abre: o curso foi encerrado |
| 3 | Treino do classificador (`artefatos/modelo.joblib`) e model gate | O `alias_local.py` serve o modelo treinado |
| 4 | Canary saudável e canary com 20% de erro, uma vez cada | As seções 1 e 2 do roteiro, sem AWS |
| 5 | Cada cenário repetido 50 vezes, contando os motivos de rollback | Uma execução só não diz se o critério é confiável |

## 1. O canary uma vez (seções 1 e 2, pelo alias local)

```text
### Canary saudável (10% do tráfego, 0% de erro), 300 requisições
versão        req.   erro %   p95 ms  previsões
v1             266     0.0%        1  {'positiva': '38%', 'negativa': '34%', 'neutra': '28%'}
v2-canary       34     0.0%        1  {'positiva': '47%', 'negativa': '29%', 'neutra': '24%'}
✅ CANARY SAUDÁVEL — pode avançar

### Canary com falha (10% do tráfego, 20% de erro), 300 requisições
versão        req.   erro %   p95 ms  previsões
v1             259     0.0%        1  {'positiva': '41%', 'negativa': '34%', 'neutra': '25%'}
v2-canary       41    17.1%        1  {'positiva': '41%', 'neutra': '32%', 'negativa': '26%'}
❌ ROLLBACK: taxa de erro do canary 17.1% (estável 0.0%)
```

Repare no canary saudável: com o **mesmo modelo** nas duas versões, as previsões `positiva` diferem 9 p.p. (47% × 38%).
É só o acaso de 34 amostras. O critério de rollback é 15 p.p.

## 2. O canary 50 vezes

| Cenário (300 requisições cada) | Rollbacks | Motivos |
| --- | --- | --- |
| saudável, 10% do tráfego | **15 de 50** (outra rodada: 16 de 50) | distribuição das previsões e latência p95, meio a meio |
| saudável, 30% do tráfego | 2 de 50 | distribuição |
| 20% de erro, 10% do tráfego | 50 de 50 | erro em todas (e distribuição em 20) |

O canary ruim é **sempre** pego. O problema é o saudável: com 10% do tráfego, o canary recebe ~30 requisições, pouco para
os critérios de distribuição (15 p.p.) e de latência (1,5× o p95). A latência aqui é um artefato do plano B: tudo
responde em ~1 ms, e qualquer oscilação do Mac passa de 1,5×. No Lambda, a latência maior dilui isso, mas a
versão recém-publicada tem *cold start* (hipótese, não testada).

## 3. O canary no Azure (App Service com deployment slot)

**Desenho** (`azure/canary-azure.sh` e `azure/app_http.py`, nesta pasta):

| Lambda (roteiro) | App Service (aqui) |
| --- | --- |
| versão imutável publicada | slot `canary` com o pacote e o `MODELO_VERSAO` da candidata |
| alias `producao` com peso 90/10 | `az webapp traffic-routing set --distribution canary=10` |
| promover (100% na nova) | `traffic-routing clear` + `slot swap` (código e configurações trocam juntos) |
| rollback (100% na estável) | `traffic-routing clear`; depois do swap, a versão anterior fica no slot (trocar de volta é instantâneo) |

- O plano **S1** (US$ 0,116/h em `brazilsouth`, preço da API pública da Microsoft) é o mais barato com slots e
  roteamento por porcentagem: o B1 da Aula 6 não tem slot.
- O `servico.handler` recebe o evento do Lambda, então o `app_http.py` (WSGI, 30 linhas) transforma cada requisição
  HTTP nesse evento, sem mudar o serviço. Testado localmente com o mesmo `gunicorn` antes de subir.
- `MODELO_VERSAO` e `ERRO_SIMULADO` **não** são *slot settings*: viajam com o código no swap, como uma versão do Lambda.

**Resultados** (`evidencias/azure-0*.log`):

| Análise (300 requisições, 10% no canary) | Canary: req. · erro · p95 | Estável: p95 | Resultado |
| --- | --- | --- | --- |
| Saudável, 1ª (canary ocioso há ~10 min) | 30 · 0% · **2.234 ms** | 508 ms | ❌ rollback **à toa**, por latência |
| Saudável, 2ª (já aquecido) | 35 · 0% · 356 ms | 391 ms | ✅ |
| Saudável, 3ª | 26 · 0% · 341 ms | 336 ms | ✅ → **swap** (1 min 07 s): produção passa a `v2-canary` |
| 20% de erro (`v3-canary`) | 34 · **17,6%** · 1.253 ms | 351 ms | ❌ **rollback**: erro, latência e distribuição (`positiva` +19 p.p.) |

- **Medidos direto, sem roteamento, os dois slots têm a mesma latência** (mediana ~300 ms; `evidencias/azure-04-latencia-direta.log`).
  O p95 alto do canary vem da **partida a frio**, não do slot.
- **Aquecer com GET não basta.** O `servico.py` só carrega o modelo na primeira previsão (POST), e o health check não
  passa por ali. Por isso o canary com falha ainda teve p95 de 1.253 ms, mesmo depois de 20 GETs.

**Problemas encontrados no caminho** (os dois corrigidos no script):

1. **`appsettings set` logo antes do deploy mata o build:** *"Deployment has been stopped due to SCM container restart"*.
   O contêiner sobe sem as dependências e cai com *"exit code 3"*. A ordem certa é deploy → esperar → configurações.
2. **O deploy síncrono estoura o gateway** (504 depois de 9 min 46 s), porque o build do scikit-learn no S1 é lento.
   Use `--async true` e acompanhe o status do deploy (`4/true` = sucesso).

## 4. Perguntas da aula

- **Com ~15 requisições por minuto, quanto tempo para ter evidência de 2% de erro com 10% de tráfego?** O canary recebe
  1,5 requisição por minuto. Para ter 95% de chance de ver **pelo menos um** erro quando a taxa real é 2%, são precisas
  n requisições com 1 − 0,98ⁿ ≥ 0,95, ou seja, **n ≈ 150, cerca de 100 minutos**. Distinguir 2% de 1% com confiança
  exige muito mais. Com as 300 requisições do laboratório (~30 no canary), a chance de ver algum erro de uma versão que
  erra 2% é de 45%: o lab só pega erros grosseiros, como os 20% do `ERRO_SIMULADO`.
- **Por que comparar a distribuição das previsões, e não só o erro?** Um modelo ruim responde **200**, mas com o rótulo
  errado. Sem o rótulo verdadeiro em produção, a mudança na distribuição é o único sinal online de que o modelo mudou de
  comportamento. A seção 2 mostra o custo: com poucas amostras, esse sinal também dispara à toa.
- **E se fosse um prompt em canary?** A saída deixa de ser um rótulo de 3 classes. A comparação passa a ser pela
  categoria do roteador, pela nota de um juiz ou pelo sinal do usuário (reabriu o chamado, pediu humano). Cada chamada
  custa tokens, então amostra grande sai cara. O ruído do LLM soma ao da amostra (ver a Aula 6). E o mesmo cliente
  precisa cair sempre na mesma versão numa conversa, coisa que o sorteio por requisição do alias não garante.

## 5. Problemas encontrados

1. **O Learner Lab da turma foi encerrado.** Afeta esta aula e o deploy da Aula 6 (Lambda). O README do repositório
   ainda diz que o capstone fica no AWS Academy. *Ação:* falar com o professor ou a coordenação.
2. **Com os critérios atuais, um canary saudável com 10% do tráfego é revertido em ~30% das vezes** (seção 2). No
   workflow, isso vira um vermelho sem motivo real. *Sugestão:* exigir um mínimo de requisições no canary antes de
   decidir (por exemplo, 100), ou usar um teste estatístico (qui-quadrado na distribuição) em vez de 15 p.p. fixos.
3. **O roteiro não menciona o `alias_local.py`.** Ele existe, está descrito no próprio arquivo como "o plano B gratuito do
   canary da Aula 4 (sem AWS)" e funciona, mas quem fica sem o Learner Lab não sabe dele.
4. **O critério de latência reverte uma candidata saudável que acabou de subir** (Azure, seção 3). Com partida a frio, a
   primeira análise deu p95 4,4× maior. O critério compara uma versão quente (a estável) com uma fria (a nova).
   *Sugestão:* aquecer a candidata com **previsões** (POST), não com o health check, antes de abrir o tráfego, ou
   descartar as primeiras requisições da análise. No serviço, carregar o modelo na importação, e não na primeira
   chamada, também resolve.
5. **O health check do serviço não exercita o modelo.** O `GET` responde sem carregar o `modelo.joblib`, então um
   health check verde não garante que a previsão funcione (nem que esteja quente).

## 6. O que não foi testado

- O workflow *Aula 4 · Canary do classificador (AWS Lambda)* e o passo a passo manual no Lambda. O equivalente
  manual rodou no Azure (seção 3), mas não como workflow do GitHub: isso exigiria uma identidade do Azure para o
  Actions (service principal ou OIDC), que não testei.
- A correção do `MODELO_VERSAO` da candidata manual (PR #4): sem Lambda, não deu para ver.

## 7. Cuidados daqui para a frente

- Os recursos criados na Aula 2 (função `classificador-avaliacoes`, alias `producao`, repositório no ECR) ficaram na
  conta do lab encerrado. Não há como apagá-los daqui.
- Os três *secrets* `AWS_*` do repositório são da sessão de 15/10 e já expiraram. Podem ser apagados.

## 8. Evidências (`evidencias/`)

| Arquivo | O que prova |
| --- | --- |
| `00-matriculas-passadas.png`, `00-learner-lab-encerrado.png` | O curso em "Matrículas passadas" e a mensagem do Vocareum |
| `01-canary-uma-vez.log` | O canary saudável promovido e o de 20% de erro revertido |
| `02-canary-50-vezes.log` | Os três cenários repetidos 50 vezes |
| `repetir_canary.sh`, `motivos_canary.sh` | Os scripts usados, para reproduzir |
| `azure-01-criar.log` | A criação do S1, do Web App e do slot `canary` |
| `azure-02-publicar.log` | Os deploys, o build morto pelo `appsettings set`, o 504 e a nova tentativa |
| `azure-03-canary-saudavel.log` | As três análises do canary saudável (rollback a frio, depois duas aprovações) e o swap |
| `azure-04-latencia-direta.log` | A latência de cada slot medida direto, sem roteamento |
| `azure-05-canary-com-falha.log` | O canary com 20% de erro e o rollback |
| `azure-06-limpeza.log` | Os recursos antes de apagar e a limpeza |
| `../azure/canary-azure.sh`, `../azure/app_http.py` | O script e o invólucro HTTP usados |
