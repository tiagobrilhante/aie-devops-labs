# Aula 1 — laboratório de CODEOWNERS

**Tempo:** 40–45 min · **Formato:** duplas · **Entrega:** um Pull Request
com mudança real em código, teste executado e revisão do *code owner*.

## Objetivo

Construir e comprovar este fluxo no GitHub:

```text
CODEOWNERS na main → branch → código + teste → Pull Request → revisão → merge protegido
```

E ver, no mesmo PR, a diferença entre **revisor solicitado** e **merge bloqueado**.

## Papéis

| Pessoa | Papel |
| --- | --- |
| **A** | cria a cópia (owner/admin), configura a proteção da `main` e revisa como *code owner* |
| **B** | colaboradora com permissão de escrita; autora do PR (branch, código, teste) |

Sem dupla? Faça tudo sozinho e siga também a seção [Sem dupla](#sem-dupla).

**Convenção:** mensagens de commit e títulos de PR seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/),
**em inglês** (`type: description`, com `feat`, `fix`, `test`, `docs`, `chore`...). O merge é sempre **Squash and merge** (o
passo 5 deixa só ele): a `main` ganha um commit por PR, com o título do PR como mensagem.

## 1. Criar a cópia e entrar nela (~10 min)

1. **A:** no repositório `aie-devops-labs`, **logado no GitHub**, clique em **Use this template → Create a new
   repository** e crie uma cópia **pública**. No plano gratuito, a proteção da `main` só vale em repositório público.
2. **A:** **Settings → Collaborators → Add people** e adicione **B**.
3. **B:** aceite o convite (e-mail ou aviso no GitHub). Sem aceitar, B ainda não tem permissão de escrita e o GitHub
   não reconhece B como *code owner*.
4. **B:** na cópia, **Code → Codespaces → Create codespace on main**. A primeira criação leva ~8–10 min: espere o
   terminal mostrar `Pronto.`. Enquanto isso, A segue no passo 2.

A proteção da branch não é copiada pelo template: a cópia nasce sem nenhuma regra.

## 2. Definir os code owners na `main` (A, pelo navegador, ~5 min)

Para pedir revisão, o GitHub usa o `CODEOWNERS` da **branch de destino** do PR (a `main`), não o da branch do PR
([documentação](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)).
Por isso ele precisa estar na `main` **antes** do PR: um `CODEOWNERS` que só existe na branch do PR não solicita
ninguém.

Abra `.github/CODEOWNERS`, clique no lápis (*Edit*) e **substitua o conteúdo inteiro** por (troque pelos *handles*
de usuário de vocês, não pelo nome):

```text
# Toda mudança pede revisão de um code owner.
# O GitHub nunca pede revisão ao autor do PR: com os dois handles, cada um revisa o outro.
* @pessoa-a @pessoa-b

# Áreas de maior risco têm regra explícita (Aulas 3 e 6)
/agente/prompts/ @pessoa-a @pessoa-b
/gitops/overlays/producao/ @pessoa-a @pessoa-b
```

**Commit changes**, com a mensagem `chore: set up code owners for the pair` (troque o `Update CODEOWNERS` que o GitHub
sugere) e **Commit directly to the `main` branch**. É o último commit direto na `main`: depois do passo 5, tudo
entra por PR.

Abra o arquivo de novo no GitHub: se aparecer um aviso de erro (*Unknown owner*), o *handle* está errado ou o
convite ainda não foi aceito.

## 3. Alterar código e rodar o teste (B, no Codespace, ~5 min)

```bash
git pull                      # traz o CODEOWNERS do passo 2
git switch -c lab/codeowners
```

No fim de `classificador/tests/test_texto.py`, acrescente (com **duas linhas em branco** antes do `def`, como nos
outros testes):

```python
def test_texto_vazio_continua_vazio():
    assert limpar("") == ""
```

Rode o teste e o mesmo lint que o CI vai rodar:

```bash
pytest classificador/tests/test_texto.py
ruff format classificador && ruff check classificador   # o format corrige linhas em branco sozinho
```

Se passar, faça commit, push e abra o PR:

```bash
git add classificador/tests/test_texto.py
git commit -m "test: cover empty text"
git push -u origin lab/codeowners
gh pr create --fill             # com um commit só, o título do PR já sai no padrão
```

## 4. Evidência 1: revisor solicitado, merge liberado (~3 min)

No PR:

- em **Reviewers**, **A** aparece solicitada pelo `CODEOWNERS`;
- o PR mexe em `classificador/**`, então dispara o **Aula 2 · CI do classificador**: espere ficar verde;
- o botão **Merge pull request** está **verde**. **Não façam o merge.** Capture a tela.

Solicitar revisão não bloqueia nada: sem uma regra na `main`, qualquer pessoa com escrita faria o merge agora.

## 5. Proteger a `main` (A, ~7 min)

**Settings → Rules → Rulesets → New ruleset → New branch ruleset:**

- **Ruleset Name:** `protect-main`
- **Enforcement status: Active.** O formulário abre em *Disabled*, e nesse estado a regra não vale.
- **Target branches → Add target → Include default branch.** Sem alvo, a regra não vale para nenhuma branch.
- **Rules:** *Restrict deletions* e *Block force pushes* (já vêm marcadas) e **Require a pull request before
  merging**, com **Required approvals: 1**, **Require review from Code Owners** e, em **Allowed merge methods**,
  só **Squash** (garante um commit no padrão por PR).
- **Não** marque *Restrict updates*: ela bloqueia até o merge. Exigir PR já impede o push direto.
- **Bypass list:** deixe vazia. Assim ninguém passa por cima da regra, nem quem é admin. A opção *Do not allow
  bypassing the above settings* só existe na proteção clássica (**Settings → Branches**), não nos rulesets.

Clique em **Create**. O GitHub pode pedir para confirmar a identidade (senha ou passkey): é normal.

## 6. Evidência 2: o mesmo PR agora está bloqueado (~3 min)

Recarregue o PR: o merge box passa a exigir a revisão (**Review required**) e o botão de merge fica bloqueado.
Capture a tela.

**B** tenta furar a regra com um push direto na `main`:

```bash
git switch main
git commit --allow-empty -m "chore: try a direct push to main"
git push origin main            # deve ser recusado
git reset --hard origin/main    # descarta o commit de teste
git switch lab/codeowners
```

A recusa esperada (vale até para quem é admin, porque a *Bypass list* está vazia):

```text
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote: - Changes must be made through a pull request.
 ! [remote rejected] ... -> main (push declined due to repository rule violations)
```

## 7. Revisão e merge (~7 min)

1. **A**, em **Files changed**, comenta uma melhoria concreta numa linha e envia em **Review changes → Request
   changes**.
2. **B** responde e envia um novo commit na mesma branch (ex.: `test: cover whitespace-only text`).
3. **A** aprova em **Review changes → Approve**. Quem abriu o PR não pode aprová-lo.
4. O merge fica disponível: **B** confere se o título do PR segue a convenção e faz **Squash and merge**.

## Sem dupla

Com uma conta só não dá para ter a revisão de outra pessoa, e a regra vai mostrar isso. Faça os mesmos passos,
com estas diferenças:

- **Passo 2:** `* @seu-handle` (e o mesmo nas duas regras de área de risco).
- **Passo 4:** nenhum revisor é solicitado, porque o GitHub nunca pede revisão ao autor do PR. Registre isso no PR.
- **Passo 5:** a exigência de *code owner* sozinha não segura você: quando quem abre o PR é o único dono dos
  arquivos, o GitHub não exige outra revisão de *code owner*. Quem bloqueia é **Required approvals: 1**, porque
  ninguém aprova o próprio PR. Não reduza para 0.
- **Passo 6:** o merge fica bloqueado de vez (**Review required** e **Merging is blocked**), e o push direto é
  recusado.
- **Passo 7:** para fazer merge (agora e no resto da disciplina), edite o ruleset e, em **Bypass list → Add
  bypass**, adicione **Repository admin** no modo **For pull requests only**. O push direto continua proibido, e o
  merge passa a oferecer um *bypass* explícito: marque-o e escreva no PR por que a exceção foi usada.

## Entrega

Na plataforma da disciplina:

- link do repositório criado a partir do template;
- link do PR.

No PR (descrição ou comentários):

- saída do `pytest`;
- captura do passo 4 (revisor solicitado e merge liberado);
- captura do passo 6 (merge bloqueado) e a saída do push recusado;
- a revisão do passo 7 (ou, sem dupla, a justificativa do *bypass*);
- respostas: qual é a diferença entre revisor solicitado e merge bloqueado? Por que o GitHub usa o `CODEOWNERS` da
  `main`, e não o da branch do PR?

## Quando travar

- *Unknown owner* no `CODEOWNERS`: use o *handle* (usuário), não o nome, e confira se o convite foi aceito.
- Nenhum revisor solicitado: o `CODEOWNERS` não está na `main` (passo 2) ou o autor do PR é o único dono.
- O merge continua liberado depois do passo 5: o ruleset está *Disabled*, sem **Target branches** ou com
  **Required approvals: 0**.
- O merge continua travado mesmo com aprovação: confira se *Restrict updates* ficou marcada.
- CI vermelho no **1 · Lint**: rode `ruff format classificador`, faça commit e push.
- Pediram senha ou token no terminal: não digite nem diga em voz alta; a aula é gravada. Chame o professor.

## Critério de sucesso

A dupla demonstra uma mudança de código em branch, teste passando, revisão de outra pessoa e merge condicionado à
aprovação, com evidência de que só solicitar o revisor não bloqueia o merge.
