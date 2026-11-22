# Aula 2 — CI/CD do classificador: o que foi feito e por quê

Registro da execução da Aula 2 nesta cópia (`tiagobrilhante/aie-devops-labs`) em 14/10/2026, sem dupla.
Materiais usados: os slides `slides/aula2/aula2.pdf` (Parte 1 e Parte 2 do laboratório), o roteiro
`roteiros/aula-02.md` e o `roteiros/setup-aws-academy.md`.

**Resultado:** o pipeline de sete etapas rodou de verdade. O CI passa no GitHub Actions, o *model gate* reprova o
lote ruim, e o classificador foi publicado no AWS Lambda (versão 1, alias `producao`), respondendo pela URL
pública.

## Linha do tempo

| # | O que foi feito | Por quê |
| --- | --- | --- |
| 1 | Leitura dos slides, do roteiro e do código do classificador | Saber o que a aula promete antes de executar, e comparar promessa com resultado |
| 2 | Conferência das execuções do CI já registradas no Actions | A etapa "ver o pipeline passar" já tinha acontecido no PR da Aula 1 |
| 3 | Etapas 3, 4 e 5 com o lote ruim, num contêiner Linux com Python 3.12 | Conferir os números do slide; o contêiner reproduz o Codespace e o CI |
| 4 | *Build* e execução local da imagem do Lambda (plano B) | Validar o caminho alternativo quando a AWS não está disponível |
| 5 | Início do Learner Lab (*Start Lab*) | O deploy precisa de uma sessão ativa da AWS |
| 6 | Cópia das credenciais do Learner Lab para os *secrets* do GitHub | O workflow de deploy autentica com elas; por serem pessoais, ficam só nos *secrets* criptografados |
| 7 | `gh workflow run "Aula 2 · Deploy do classificador (AWS Lambda)"` | Etapa 7: publicar o modelo aprovado |
| 8 | Chamadas à URL pública | Provar que o serviço publicado responde, além do *smoke test* do workflow |
| 9 | Teste do PR "sem commits" do roteiro, com uma branch temporária (já apagada) | Conferir uma instrução do roteiro que parecia não funcionar |

## 1. O pipeline em uma figura

```text
1 Lint ──┬── 2 Testes unitários ──┬── 4 Treino ── 5 Model gate ── 6 Build da imagem      (ci-classificador.yml)
         └── 3 Testes de dados ───┘
                                                   7 Deploy no Lambda + smoke test     (deploy-classificador.yml)
```

- `ci-classificador.yml` roda as etapas 1 a 6 em todo PR que mexe em `classificador/**`, em todo push na `main`
  com essa mesma condição e sob demanda (`workflow_dispatch`).
- `deploy-classificador.yml` refaz o treino e o gate antes de publicar, para que nada chegue à produção sem
  passar por eles. Ele roda sob demanda e também em push na `main` que mexa em `classificador/**`. Veja o
  problema 1 na seção 4.

## 2. Parte 1 (desenho): a tabela da Proposta A, preenchida a partir do código

A Parte 1 é discussão em grupo e não tem nada para executar. A tabela abaixo mostra **o que este repositório já
implementa**, para servir de referência ao desenho:

| Etapa | O que valida | Critério de aprovação (o `if`) | Se falhar |
| --- | --- | --- | --- |
| Lint | Estilo, erros e imports (`ruff`, regras E, F, I, W) e formatação | `ruff check` e `ruff format --check` sem erro | Job vermelho; as outras etapas nem rodam |
| Testes unitários | Limpeza de texto (`classificador/texto.py`) | 100% dos testes de `test_texto.py` passam | Job vermelho |
| Testes de dados | Schema, texto vazio, rótulos válidos, volume, textos só com emoji, distribuição das classes | ≥ 300 linhas; ≤ 10% de textos sem palavra; cada classe a no máximo 10 p.p. da referência (40/35/25%) | Bloqueia. Um desvio entre 5 e 10 p.p. só **alerta** (`warnings.warn`) |
| Build | A imagem do Lambda constrói com o modelo treinado | `docker build` termina sem erro | Job vermelho; sem imagem não há deploy |
| Model gate | F1 do candidato no conjunto de validação | F1 macro ≥ 0,80; F1 de **cada** classe ≥ 0,70; queda ≤ 0,02 em relação à produção (`producao.json`, 0,82) | `exit 1`: o pipeline para e nada é publicado |
| Deploy | Nova versão imutável no Lambda, alias `producao` e *smoke test* | `curl -f` na URL pública responde 2xx | Job vermelho (mas o tráfego já foi trocado; veja o problema 7) |
| Observabilidade | **Não implementada** para o classificador neste repositório | — | — |

"Job vermelho" só **bloqueia o merge** se o check for obrigatório no ruleset da `main` (veja o problema 8).

## 3. Parte 2 (prática): o que foi executado e o resultado

### 3.1 O CI roda sozinho

Não foi preciso disparar nada: o CI já tinha rodado no PR #1 (evento `pull_request`) e no merge dele (evento
`push` na `main`). As etapas 1 a 6 ficaram verdes, em cerca de 1 min 40 s.

### 3.2 O lote "que parece normal" (etapas 3, 4 e 5)

**Onde rodou:** num contêiner `python:3.12-slim`, com as dependências de `requirements.txt`. **Por quê:** o
`scipy==1.15.3` não carrega neste macOS (erro do `dyld`), e um Linux com Python 3.12 é o mesmo ambiente do
Codespace e do runner do GitHub.

Primeiro, a base saudável, para ter a referência:

```text
$ python classificador/treino.py && python classificador/model_gate.py artefatos/metricas.json
Candidato: F1 macro 0.8295 · por classe {'positiva': 0.8835, 'negativa': 0.8125, 'neutra': 0.7925}
✅ MODEL GATE APROVOU
```

Depois, o lote novo, na ordem do pipeline:

```text
$ DADOS=classificador/dados/lote-novo.csv pytest classificador/tests/test_dados.py      # etapa 3
3 falhas, 5 testes passam, 2 alertas:
  - 28% dos textos só têm emojis (máx. 10%)
  - classe 'neutra' em 9%, referência 25% — drift de rótulo
  - classe 'positiva' em 52%, referência 40% — drift de rótulo

$ python classificador/treino.py --dados classificador/dados/lote-novo.csv              # etapa 4
F1 macro 0.731 · positiva 0.8291 · negativa 0.7805 · neutra 0.5833

$ python classificador/model_gate.py artefatos/metricas.json                            # etapa 5
❌ MODEL GATE REPROVOU:
   - F1 macro 0.731 < 0.8
   - F1 da classe 'neutra' 0.5833 < 0.7
   - piora de 0.0890 no F1 macro em relação à produção (0.82)
```

Os números do slide conferem (F1 macro 0,73 e *neutra* 0,58).

**Para a discussão da aula:**

- **O que barrou primeiro?** O teste de dados (etapa 3), antes de gastar tempo treinando. O gate (etapa 5) é a
  segunda barreira: ele pega o efeito do lote ruim no modelo.
- **Qual regra bloqueia e qual só alerta?** Em `test_dados.py`, o que está em `assert` bloqueia; o
  `warnings.warn` só alerta. Na distribuição das classes, mais de 5 p.p. de desvio gera alerta e mais de 10 p.p.
  bloqueia. No lote novo, *neutra* (−16 p.p.) e *positiva* (+12 p.p.) alertam **e** bloqueiam; *negativa* fica
  dentro da margem.
- **Mudar um limite:** o gate exige um piso **por classe** (0,70) porque a média esconde a classe ruim. Com
  F1 macro 0,731, um gate só pela média, com limite 0,70, aprovaria um modelo com F1 de apenas 0,58 na classe
  *neutra*.

### 3.3 Deploy no AWS Academy (etapa 7)

1. **Learner Lab ligado.** Aceitei os termos da Vocareum; o *Start Lab* levou de 3 a 4 minutos na primeira vez.
   O painel mostra a sessão de 4 h e o crédito: **US$ 50**.
2. **Credenciais nos *secrets* do GitHub.** Em *AWS Details → AWS CLI: Show*, copiei os três valores para
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN`, e conferi com `gh secret list`, que mostra
   só os nomes. **Por quê assim:** são credenciais pessoais; ficam só nos *secrets* criptografados do repositório,
   nunca num arquivo ou numa mensagem.
3. **Environment `producao`:** já existia. O GitHub o criou sozinho na primeira execução do workflow de deploy.
4. **Deploy:** `gh workflow run "Aula 2 · Deploy do classificador (AWS Lambda)"`. A execução levou cerca de
   2 minutos, e todas as etapas passaram:
   - treino e gate de novo: F1 macro 0,8295, aprovado;
   - validação das credenciais (`aws sts get-caller-identity`);
   - `classificador/deploy/publicar.sh`: criou o repositório `classificador-avaliacoes` no ECR, enviou a imagem
     com a tag do commit (`a171272`), criou a função Lambda com a `LabRole` (a única *role* que o Learner Lab
     permite usar) e publicou a **versão 1**, que é imutável;
   - `classificador/deploy/trafego.sh 1`: criou o alias `producao` apontando para a versão 1, a Function URL
     pública e as duas permissões que a AWS exige para chamá-la sem autenticação;
   - *smoke test*: um `POST` na URL, que respondeu 200.
5. **Testes manuais na URL pública** (o endereço está no resumo da execução, na aba *Actions*):

| Texto enviado | Resposta |
| --- | --- |
| `Adorei, chegou rápido` | `positiva`, confiança 0,79 |
| `Péssimo, veio quebrado e ninguém responde` | `negativa`, confiança 0,93 |
| `Chegou no prazo, produto conforme a descrição` | `neutra`, confiança 0,78 |
| `{"text": "oi"}` (campo errado) | HTTP 400, `envie {"texto": "..."}` |

Todas as respostas trazem `"versao": "a171272"` e o cabeçalho `x-modelo-versao`. É assim que se sabe qual
versão atendeu, o que a Aula 4 (canary) vai usar.

### 3.4 Plano B: o mesmo contêiner, localmente

Os comandos do slide funcionam (treinar, `docker build`, `docker run -p 9000:8080`), mas o slide não diz como
**chamar** o contêiner. Testado:

| Chamada | Resultado |
| --- | --- |
| `curl -X POST http://localhost:9000 -d '{"texto": "..."}'` | 404 |
| Endereço do emulador, com `{"texto": "..."}` | 400 `envie {"texto": "..."}`, mesmo com o texto lá |
| Endereço do emulador, com o evento da Function URL | 200, `positiva` |

O jeito certo:

```bash
curl -s -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"body": "{\"texto\": \"Adorei, chegou rápido\"}"}'
```

**Por quê:** a imagem base do Lambda traz um emulador que espera o **evento** do Lambda, não a requisição HTTP.
Na Function URL, o corpo chega como texto dentro do campo `body`, e é isso que o `servico.handler` lê.

## 4. Problemas encontrados nos materiais (com evidência)

1. **O deploy dispara sozinho a cada push na `main` que mexe em `classificador/**`.** O roteiro diz que ele é
   manual. Nesta cópia, ele falhou na criação a partir do template e no merge do PR da Aula 1, por falta de
   credenciais. O erro vem do `configure-aws-credentials` (*"Could not load credentials from any providers"*),
   antes da mensagem amigável que o workflow tem. O deploy do agente (Aula 6) também falhou na criação da cópia.
   *Sugestão:* tirar o `push` do `on:` ou condicionar o job a uma variável (`if: vars.DEPLOY_AWS == 'true'`).
2. **"Se você usa a cópia da Aula 1" não funciona como está.** Uma branch sem commits novos não vira PR:
   `gh pr create --fill` falha com *"could not find any commits between origin/main and …"*, e sem `--fill` o
   GitHub responde *"No commits between main and …"*. *Sugestão:* disparar o CI com
   `gh workflow run "Aula 2 · CI do classificador"` (o workflow aceita disparo manual) ou fazer o Desafio numa
   branch e abrir o PR com ele.
3. **"1. Ver o pipeline passar: `git push`".** Numa cópia recém-criada não há o que enviar
   (*Everything up-to-date*), e com a `main` protegida da Aula 1 o push direto é recusado. *Sugestão:* a mesma do
   item 2, seguida de `gh run watch`.
4. **O plano B não diz como chamar o contêiner** (seção 3.4).
5. **O crédito do Learner Lab desta turma é US$ 50**, não os US$ 100 do `setup-aws-academy.md`.
6. **"Crie também o environment `producao`"** é desnecessário: o GitHub cria sozinho na primeira execução.
7. **O *smoke test* roda depois de mandar 100% do tráfego para a versão nova.** Se ele falhar, a versão quebrada
   já está no ar e nada a desfaz. *Sugestão:* testar a versão antes de mover o alias, ou devolver o alias à versão
   anterior quando o teste falhar. É o assunto da Aula 4 (canary).
8. **"Bloqueia o PR" (slide da Proposta A) só vale com *Require status checks to pass* no ruleset da `main`.**
   Sem isso, o CI vermelho é só um aviso. Atenção: o CI usa filtro de caminho (`classificador/**`). Um check
   obrigatório num PR que não mexe nessa pasta nunca é reportado e deixa o PR esperando para sempre.
9. **Detalhes do slide:** o lote tem 27,5% de textos só com emoji (o slide diz 30%), e o gate dá três motivos de
   reprovação (o slide cita dois).
10. **A URL pública, sem autenticação, aparece no resumo do Actions**, que num repositório público qualquer
    pessoa lê. O custo por chamada é mínimo, mas sai do crédito do lab. Vale apagar a função ao fim da disciplina
    (passo 5 do `setup-aws-academy.md`).

## 5. O que não foi testado

- **Credenciais expiradas** (fim da sessão de 4 h): não deu para esperar. Sem credenciais, o erro aparece antes
  da mensagem amigável (problema 1).
- **URL com o lab encerrado** (o setup relata HTTP 502): não testado nesta sessão.
- **O Desafio** (checagem do tamanho médio do texto): feito depois, em 22/11/2026 (seção 7).
- **Um Codespace de verdade:** no lugar dele, usamos um contêiner Linux com Python 3.12 e o runner do GitHub.

## 6. Cuidados daqui para a frente

- As credenciais valem **só para esta sessão** do Learner Lab. A cada *Start Lab*, copie de novo os três valores
  para os *secrets* antes de rodar um deploy.
- O Learner Lab guarda o que foi criado entre sessões. A função `classificador-avaliacoes`, o alias `producao` e
  o repositório no ECR continuam lá para a Aula 4, que publica uma versão 2 e faz o canary.
- Limpeza ao fim da disciplina: `roteiros/setup-aws-academy.md`, passo 5.

## 7. Desafio: tamanho médio do texto (22/11/2026, PR #10)

Enunciado (`roteiros/aula-02.md`; não aparece nos slides): *"Adicione ao `test_dados.py` uma checagem de tamanho do texto
(média de palavras por avaliação dentro de ±30% da base de treino) e faça o lote-novo falhar também por ela."*

**As duas exigências se contradizem com estes dados:** o `lote-novo.csv` está a **−27,8%** da base de treino, então com
±30% ele **passa**. Medido:

| Arquivo | Média de palavras (depois de `texto.limpar`) | Em relação ao treino |
| --- | --- | --- |
| `avaliacoes.csv` (treino) | 11,15 | 0% |
| `validacao.csv` | 11,56 | +3,7% |
| `lote-novo.csv` | 8,05 | **−27,8%** |

O ruído da média num lote de 300 linhas (o volume mínimo que o teste aceita), estimado por *bootstrap* da base de
treino, fica abaixo de 6,5% em 99% das vezes. Qualquer limite entre ~10% e ~25% separa o ruído do lote ruim.

**Decisão:** `test_tamanho_medio_do_texto`, no mesmo padrão do teste de classes: **alerta acima de 10%**
(`warnings.warn`) e **bloqueio acima de 20%** (`assert`). A contagem usa o `texto.limpar`, a mesma limpeza que o modelo
vê, e a referência (11,15) fica fixa no arquivo, como a `REFERENCIA` das classes.

```text
$ DADOS=classificador/dados/lote-novo.csv pytest classificador/tests/test_dados.py
AssertionError: média de 8.1 palavras por texto, referência 11.15 (-28%) — drift de tamanho
UserWarning: média de 8.1 palavras por texto (-28% da referência)
```

**Ressalva:** a queda vem toda dos 27,5% de textos só com emoji. Sem eles, o lote tem 11,65 palavras de média. Por isso
o teste novo se sobrepõe ao `test_proporcao_de_textos_so_com_emojis`. Mesmo assim, é um sinal independente, que também
pegaria um lote de textos curtos ou truncados *com* palavras.

Evidência: `evidencias/desafio-tamanho-do-texto.log`.
