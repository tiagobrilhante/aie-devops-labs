# Aula 4 — propostas de rollout para os dois cenários (rascunho para o capstone)

> Rascunho. A Parte 1 do laboratório da Aula 4 pede, para cada cenário: **1.** a estratégia (ou combinação), **2.** as
> métricas de decisão e o que dispara o rollback automático, **3.** uma frase justificando a escolha em vez das outras
> quatro (Aula 04, p. 23). *"Este exercício alimenta diretamente o eixo de rollout do capstone"* (p. 20).
> As cinco estratégias vistas: canary, blue-green, shadow, feature toggle e A/B test (p. 14).

## O que os laboratórios mediram (e que muda as propostas)

| Fato medido | Onde | Consequência para o desenho |
| --- | --- | --- |
| Com 10% do tráfego e 300 requisições (~30 no canary), um canary **saudável** sofre rollback em **15 a 16 de 50** execuções; com 30%, em 2 de 50. Metade por distribuição, metade por latência | `../aula4/README.md`, seção 2 | Decidir por **amostra mínima**, não por relógio nem por número fixo de requisições totais |
| A versão que erra 20% foi pega em **50 de 50** execuções | idem | O critério pega erro grosseiro com folga |
| Para ter 95% de chance de ver ao menos um erro de uma versão que erra 2%: **n ≈ 150** requisições **no canary** (1 − 0,98ⁿ ≥ 0,95). Com ~30 requisições, a chance é de 45% | `../aula4/README.md`, seção 3 | Com 15 req/min e 10% de tráfego, ~100 min por degrau |
| O agent gate **aprovou** uma queda de 83% para 50% em `fraude_vendedor` (variante D) porque a média subiu de 86% para 92% | `../aula6/README.md`, seção 2 | Métrica **por categoria**, nunca só a média |
| No runner do GitHub, o mesmo prompt oscila até 2 casos por categoria; no Mac (Metal), 3 execuções deram **0 casos diferentes** | `../aula6/README.md`, seção 2 | O ruído depende do hardware; a tolerância precisa ser medida onde o gate roda |
| O mesmo prompt ruim deu resposta média de 72% no Mac e 64% no runner | `../aula6/README.md`, seção 3 | Comparar canary e estável **no mesmo ambiente**, nunca contra um número de outro lugar |

## Cenário 1 — modelo de risco de fraude no checkout (Aula 04, p. 21)

Modelo de classificação que aprova ou barra uma compra **em tempo real**; a versão nova tem métricas offline melhores e
nunca viu tráfego de produção.

**1. Estratégia: shadow → canary em degraus, atrás de um feature toggle (kill switch).**

- **Shadow:** o modelo novo pontua todas as compras em paralelo, mas quem decide continua sendo o vigente. Risco zero
  para o cliente, e mede o modelo novo com tráfego real.
- **Canary em degraus** (por exemplo 1% → 10% → 50% → 100%), cada degrau só depois da amostra mínima e dos critérios.
- **Feature toggle:** desliga o modelo novo em segundos, sem deploy, se algo der errado fora dos critérios automáticos.

**2. Métricas de decisão e rollback automático**

| Fase | Métrica | Avança se | Rollback automático se |
| --- | --- | --- | --- |
| Shadow | concordância de decisão (aprova/barra) com o modelo vigente | divergência dentro do esperado pelas métricas offline | — (shadow não afeta o cliente; só não avança) |
| Shadow | taxa de bloqueio do modelo novo × vigente | diferença ≤ limite definido pelo negócio | — |
| Shadow e canary | latência p95 (decisão em tempo real) | ≤ 1,5 × a do vigente (critério do `canary_check.py`) | p95 > 1,5 × a do vigente **com amostra mínima** |
| Canary | taxa de erro técnico | ≤ 2% e no máximo +1 p.p. sobre o estável | > 2% **com amostra mínima** |
| Canary | taxa de bloqueio (proxy sem rótulo) | diferença ≤ limite em p.p. | diferença acima do limite com amostra mínima |
| Depois | fraude confirmada (chargeback) e compras legítimas barradas | — | chega com semanas de atraso: confirma depois, não decide o canary |

**Em quanto tempo a 100%:** depende do volume do checkout (*a confirmar*). A regra é por amostra: cada degrau precisa de
pelo menos ~150 requisições **no canary** (o mínimo para ver um erro de 2% com 95% de chance). O tempo por degrau é
150 ÷ (requisições por minuto × fração do canary). Com o volume do laboratório (15 req/min, 10%), ~100 min por degrau.
Com volume real de checkout, o shadow e os primeiros degraus cabem em horas.

**3. Justificativa:** num domínio de alto risco (dinheiro do cliente e da loja), o shadow é a única estratégia que mede
o modelo com tráfego real **sem** decidir nenhuma compra (Aula 04, p. 14); o canary vem depois, com a amostra que o
laboratório mostrou ser necessária. Blue-green trocaria 100% de uma vez; A/B test responde "é melhor para o negócio?",
não "é seguro?" (p. 18–19).

## Cenário 2 — novo prompt do agente de atendimento, com política de reembolso mais restrita (Aula 04, p. 22)

O time suspeita que o prompt novo fique mais "seco" ou **recuse pedidos que deveria atender**.

**1. Estratégia: agent gate antes do deploy → canary por sessão (fixa por conversa), atrás de um feature toggle.**

- **Agent gate** (Aula 6) no PR: golden dataset por categoria e camada. Barra a regressão grosseira antes de qualquer
  cliente ver.
- **Canary por sessão:** uma fração das **conversas** recebe o prompt novo, e a mesma conversa fica na mesma versão até o
  fim (Aula 04, p. 16).
- **Feature toggle:** a versão do prompt é configuração (`PROMPT_VERSAO` no GitOps ou o alias `@producao` no Prompt
  Registry). Voltar é mudar a configuração: no laboratório da Aula 3, o `git revert` levou **20 s** até produção.

**2. Métricas de decisão e rollback automático**

| Fase | Métrica | Avança se | Rollback automático se |
| --- | --- | --- | --- |
| Agent gate (PR) | roteamento, recuperação e resposta **por categoria** | todas ≥ piso de `limites.yaml` (50%) e nenhuma regressão > tolerância | — (bloqueia o merge) |
| Agent gate (PR) | **recusas indevidas:** casos do golden em que a política **permite** o reembolso | taxa igual à da versão vigente | — (bloqueia o merge). *Precisa criar esses casos no golden* |
| Canary | taxa de escalonamento para humano (Aula 04, p. 16) | dentro do limite em p.p. sobre o estável | acima do limite, **por categoria**, com amostra mínima |
| Canary | taxa de sucesso na tarefa / uso correto de ferramentas (p. 16) | igual ou melhor | pior além do limite, com amostra mínima |
| Canary | reabertura do chamado ou pedido de atendente humano | dentro do limite | acima do limite |
| Canary (amostra) | juiz de fidelidade: contradição com a política | sem contradição nova | contradição confirmada (exige juiz forte, ver abaixo) |

**3. Justificativa:** a regressão de um prompt é silenciosa (*"funciona, só que pior"*, Aula 04, p. 15), então o
primeiro filtro é offline (o gate); online, o canary por sessão limita quantas conversas sofrem com uma recusa indevida,
e o toggle volta em segundos. Blue-green só serve se o prompt novo mudar a interface a ponto de não poder conviver com o
antigo (p. 17); A/B test responde se converte melhor, não se recusa quem não devia (p. 18).

## O que muda só por ser um prompt (pergunta do cenário 2)

1. **O critério passa de asserção a amostragem** (Aula 04, p. 15). A saída não é um rótulo de 3 classes: é texto. A
   comparação vira categoria do roteador, escalonamento, juiz.
2. **O ruído do LLM se soma ao da amostra.** No runner, até 2 casos por categoria mudam entre execuções do mesmo
   prompt. A tolerância de 2 em 6 deixa passar uma queda real de 2 casos (variante D da Aula 6).
3. **A média engana.** Uma categoria pode cair muito enquanto a média sobe: o gate e o canary precisam olhar **por
   categoria**.
4. **O juiz também erra.** O juiz de 3B deu alarmes absurdos (papagaio, bolsa); o de 32B acabou com eles e pegou a
   contradição real (o Pix), mas os dois reprovam omissões que a rubrica aceita. Para virar critério de rollback,
   precisa de modelo forte e de rubrica revisada.
5. **A sessão precisa ficar presa à versão.** O sorteio por requisição do alias do Lambda (e do `alias_local.py`) não
   garante isso; para conversa, o roteamento é por sessão.
6. **O artefato é texto, e a linhagem pode mentir.** No Prompt Registry da Aula 5, uma versão foi registrada com um
   commit que não contém o texto dela. O rollback precisa apontar para uma versão cujo texto está no Git.
7. **Custo por requisição.** Cada amostra do canary custa tokens. O grafo completo do Quantum Atende mediu ~32 mil
   tokens de entrada por chamado.

## Em andamento

- **Canary da Aula 4 no Azure** (App Service com *deployment slot*, 10% do tráfego; `../aula4/README.md`, seção 3):
  o canary com 20% de erro foi revertido. O saudável foi **revertido à toa na primeira análise**, por latência de
  partida a frio (p95 de 2.234 ms contra 508 ms), e aprovado nas duas seguintes, já aquecido. Para os dois cenários:
  **aquecer a candidata com previsões de verdade antes de abrir o tráfego**. O health check não carrega o modelo, então
  aquecer com ele não adianta.
- **Integração leve do Quantum Atende no gate** (PR #11; `integracao-quantum-atende/README.md`): o roteador do grupo acerta
  91% das 180 reclamações reais (o do template, 76%), mas 75% das 36 dúvidas de política (o do template, 86%). Para o
  cenário 2, as métricas de decisão precisam vir do **tráfego real** (reclamações), por categoria.

*A confirmar com o enunciado da Aula 6:* se a estratégia de rollout do capstone é a do cenário 2 (o agente da Quantum) e
qual o formato da entrega.
