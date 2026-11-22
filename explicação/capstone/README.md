# Capstone — rascunhos de preparação

> **RASCUNHO.** O enunciado oficial do trabalho final (entregáveis 3 a 6, critérios, pesos, formato e prazo) só é
> apresentado **no começo da Aula 6** (slides da Aula 00, p. 17). Nada aqui substitui esse enunciado. Tudo o que depende
> dele está marcado como **"a confirmar com o enunciado da Aula 6"**.

Escrito em 22/11/2026 a partir do que os laboratórios das Aulas 2 a 6 **mediram** nesta cópia (relatórios em
`../aulaN/README.md`, com evidências em `../aulaN/evidencias/`).

## O que já se sabe

- **É em grupo:** "os mesmos grupos do capstone" (Aula 04, p. 20). O grupo é o **Tenho Medo de Grupos**, o mesmo do
  trabalho final de *Agents, Multi-Agents & Interoperability* (o multiagente "Quantum Atende"):
  - Tiago da Silva Brilhante
  - Gabriel Moreira do Nascimento
  - Andrew Augusto Jungers da Silva
  - Getter Benedito de Matos Fernandes
- **É um capítulo do projeto integrador Quantum Commerce** (Aula 00, p. 15). A missão desta disciplina: o pipeline que
  testa o comportamento dos agentes antes de cada atualização no site da Quantum (Aula 05, p. 42).
- **Os entregáveis, pelo `roteiros/aula-06.md`:**

| # | Entregável | Onde está hoje |
| --- | --- | --- |
| 1 e 2 | Este repositório: esteira + golden dataset + agent gate funcionando | Funciona. A troca pelo Quantum Atende (roteador + BM25 do grupo, golden de 180 reclamações) está no **PR #11**: ver `integracao-quantum-atende/` |
| 3 | `gitops/` (repositório de configuração) | Esqueleto em [`entregaveis-3-a-6-esqueleto.md`](entregaveis-3-a-6-esqueleto.md) |
| 4 | Estratégia de rollout | Rascunho em [`aula4-propostas-de-rollout.md`](aula4-propostas-de-rollout.md) |
| 5 | Book de métricas | Esqueleto em [`entregaveis-3-a-6-esqueleto.md`](entregaveis-3-a-6-esqueleto.md) |
| 6 | Pitch | Só a estrutura; a duração não aparece nos slides |

- **Os slides mandam guardar três exercícios para o capstone:**
  - o diagrama da esteira (Aula 02, p. 20) → [`aula2-diagrama-da-esteira.md`](aula2-diagrama-da-esteira.md);
  - a proposta de rollout dos dois cenários (Aula 04, p. 20 e 24) → [`aula4-propostas-de-rollout.md`](aula4-propostas-de-rollout.md);
  - o desenho de registro e promoção (Aula 05, p. 20) → [`aula5-desenho-do-registry.md`](aula5-desenho-do-registry.md).

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| [`aula2-diagrama-da-esteira.md`](aula2-diagrama-da-esteira.md) | As sete etapas, as etapas 3 e 5 detalhadas com os limites reais, e a decisão sobre o `lote-novo.csv` |
| [`aula4-propostas-de-rollout.md`](aula4-propostas-de-rollout.md) | Os dois cenários da Aula 4 (modelo de fraude no checkout e prompt do agente de reembolso) |
| [`aula5-desenho-do-registry.md`](aula5-desenho-do-registry.md) | Os quatro itens do desenho de registry da Aula 5 |
| [`entregaveis-3-a-6-esqueleto.md`](entregaveis-3-a-6-esqueleto.md) | Esqueleto de `gitops/`, rollout, book de métricas e pitch |

## Pontos em aberto para o grupo

1. **O enunciado da Aula 6:** entregáveis 3 a 6, critérios, formato (documento, slide, vídeo?), prazo e local de
   entrega. *A confirmar com o enunciado da Aula 6.*
2. **Qual agente vai para o gate:** a integração leve do Quantum Atende (classificador + busca BM25 do projeto, uma
   chamada de LLM por chamado) está no PR #11, com as medições em `integracao-quantum-atende/README.md`. O grafo completo (~4,5 chamadas e ~32 mil tokens de entrada por
   chamado, medido pelo grupo com o Claude) não cabe no CI com um modelo de 3B.
3. **Qual base de políticas vale:** a do template (`agente/politicas/*.md`, 6 arquivos) ou a do Quantum Atende
   (`dados/central-documentos/`, `pol-*.md`)? As camadas de recuperação e de resposta do gate dependem disso.
4. **Onde o agente roda em produção:** o AWS Academy da turma foi encerrado; o deploy da Aula 6 foi feito no Azure Web
   Apps (e apagado). E qual LLM em produção: o agente publicado usou o provedor `simulado`.
5. **Governança do repositório:** o slide da Aula 01 (p. 37) pede *"Do not allow bypassing"*, mas no modo solo o merge
   só sai com o *bypass* do admin. Com o grupo no repositório, dá para tirar o *bypass* e ter revisão de verdade.
