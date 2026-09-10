---
name: calculo-cycle-time
description: Regras e fórmulas de cálculo de Cycle Time, Lead Time, MTTR e Frequência de Entrega usadas no dashboard "Obeya Engenharia" (Produtividade/Qualidade/Eficiência). Use isso antes de calcular, alterar ou explicar qualquer uma dessas métricas, para manter a definição consistente entre o protótipo, o script de extração e qualquer relatório derivado.
---

# Cálculo de Cycle Time e métricas relacionadas

Especificação definitiva, confirmada por Gláucia em 09/2026 (substitui a
versão anterior baseada em "tempo corrido cru"). Aplica-se em dias/horas
**úteis**, descontando bloqueios.

## Definições

- **Cycle Time de Valor** — tempo decorrido desde a primeira entrada do card
  em um status de execução até sua conclusão, em dias úteis. Escopo de tipo:
  `Sprint Task` + `User Story` + `Spike`.
- **Cycle Time de Issue** — mesma fórmula, aplicada só ao tipo `Issue`. Isso
  **substitui** o antigo cálculo de MTTR (não são mais duas fórmulas
  diferentes) — a chave `mttr_horas` no JSON de saída continua existindo por
  compatibilidade, mas seu valor agora é o Cycle Time de Issue convertido pra
  horas (`dias_úteis × 8`).
- **Lead Time** — mesma lógica de desconto (bloqueio + calendário útil), mas
  início = **criação** do card, não a primeira execução. `Criação → conclusão
  = Lead Time`; `Execução → conclusão = Cycle Time`. Nunca usar data de
  criação para Cycle Time.
- **Frequência de Entrega** — segue usando o mapeamento por projeto em
  `TFS_TYPE_MAP_JSON` (skill `tfs-devices-ndd`), que é **diferente** do escopo
  de tipo do Cycle Time de Valor acima (esse inclui `Sprint Task`, aquele
  não). São dois recortes propositalmente distintos — não confundir.

## Fórmula

```
Início (execução) = primeira entrada em um estado de execução:
    Active, In Development, In Progress, Doing, Em andamento (lista pode
    crescer — cada tipo/projeto pode ter nomes próprios; ver --list-states)

Início (lead time) = System.CreatedDate (criação do card)

Fim = PRIMEIRA entrada em `Resolved` OU `Closed`
    (nome literal do estado — não é "categoria Completed" do TFS; em alguns
    templates "Resolved" tem categoria InProgress mas ainda conta como fim
    aqui. Usamos a PRIMEIRA ocorrência — decisão revisada em 09/2026, ver
    "Confirmado por Gláucia" abaixo — ignora deliberadamente reabertura e
    retrabalho depois do primeiro fechamento.)

Tempo bloqueado = soma dos intervalos em que, no histórico do item:
    - o campo Microsoft.VSTS.CMMI.Blocked indica bloqueio, OU
    - o campo System.Tags contém alguma destas tags (lista confirmada por
      Gláucia, 09/2026): Bloqueado, #Bloqueado, Bloqueio, Bloqueado -
      Prioridade, Bloqueado - Ambiente/Infra, Bloqueado - Outros Times,
      Bloqueado - Pendência Técnica, "blo", Bloqueada
    Cada intervalo vai do momento em que a condição de bloqueio passou a
    valer até o momento em que deixou de valer (ou até o "Fim" do item, se
    ainda estava bloqueado quando concluiu).
    IMPORTANTE (bug corrigido em 09/2026): tag e campo são combinados com OU
    — o item só volta a "não bloqueado" quando NENHUMA das duas condições
    vale mais. Se a tag for removida antes do campo (ou vice-versa), o
    bloqueio continua até a segunda remoção. A primeira versão do código
    fechava o intervalo assim que qualquer uma das duas fontes indicasse
    "não bloqueado", subcontando o tempo de bloqueio nesses casos.

Horas úteis brutas = horas úteis entre Início e Fim
    (08:00–17:00, descontando 1h de almoço → 8h úteis/dia; sáb/dom não
    contam; feriados da tabela abaixo não contam)

Horas úteis líquidas = Horas úteis brutas − horas úteis dentro dos
    intervalos de bloqueio (interseção com a janela Início–Fim)

Cycle/Lead Time (dias úteis) = Horas úteis líquidas ÷ 8
```

**Filtro de ruído**: resultado ≤ 0,01 dia útil é descartado (não entra na
média) — normalmente indica transição automática/instantânea, não trabalho
real.

## Calendário de feriados 2026 (ndd)

01/01, 03/04 (Paixão de Cristo), 21/04, 01/05, 07/09, 12/10, 02/11, 15/11,
20/11, 25/12, 04/06 (Corpus Christi). Fins de semana são sempre não-úteis,
independente desta lista.

## Confirmado por Gláucia (09/2026)

1. **Sem fallback por categoria** (decisão de 09/2026, substitui a regra
   anterior): Início e Fim só contam quando o item passou **literalmente**
   por um nome de `EXEC_START_STATES`/`END_STATES` no histórico — a
   categoria de estado (`Completed`/`InProgress`) nunca é usada como
   substituto. Precisão importante: as duas ausências têm efeitos
   diferentes no cálculo, não são a mesma coisa —
   - sem **fim** literal (`Resolved`/`Closed`): item inteiro fora de
     Frequência de Entrega, Defeitos, Cycle Time, Lead Time e MTTR daquele
     mês (o bucket exige `end_done` pra existir).
   - sem **início de execução** literal, mas COM fim literal: ainda conta
     em Frequência de Entrega/Defeitos (o fim é confiável) e em **Lead
     Time** (que só depende de criação→fim), só fica de fora do **Cycle
     Time**/**MTTR** (que dependem do início de execução).
   O JSON de saída carrega `fim_literal_ausente` e
   `inicio_exec_literal_ausente` separados — não conflatar os dois num
   único "sem dado" ao consumir o JSON (bug já cometido uma vez no
   protótipo: o export pro dashboard zerava Lead Time também quando só
   faltava o início de execução).
2. **Campo de bloqueio**: `Microsoft.VSTS.CMMI.Blocked == "Yes"` (comparação
   exata, case-insensitive) — qualquer outro valor (`"No"`, vazio, etc.) não
   conta como bloqueio.
3. **Revisado em 09/2026** (substitui a decisão anterior de usar a última
   entrada): usar a **primeira** entrada em Resolved/Closed, não a última.
   Motivo: Gláucia trouxe a regra de uma dash anterior dela (Claude Chat,
   card "O que mede: Tempo útil médio do início ao fim da entrega") já
   validada contra a outra ferramenta de referência da ndd (~7-8 dias de
   Cycle Time) — essa dash usa primeira entrada, e ignora deliberadamente
   o tempo entre um primeiro fechamento e uma reabertura/retrabalho
   posterior. Provável explicação da cauda longa (itens com >200 dias
   úteis) documentada abaixo — a confirmar depois do reprocessamento com
   essa regra.

## Ainda em aberto

- **Lista de estados "de execução"** (`Active, In Development, In Progress,
  Doing, Em andamento`) foi dada como exemplo ("etc."). Pode não cobrir todo
  tipo/projeto — o script loga quantos itens ficaram **fora do cálculo** por
  falta de estado literal a cada rodada; se esse número for alto,
  provavelmente falta nome de estado nessa lista (e não indica bug, já que
  não há mais fallback pra mascarar isso).
- **Cauda longa observada com a regra antiga (última entrada em
  Resolved/Closed)**: alguns itens tinham Cycle Time de centenas de dias
  (ex.: WI-208 com 227,7d, WI-598 com 265,2d), quase sem hora bloqueada
  registrada no intervalo. Hipótese mais provável, levantada por Gláucia:
  eram itens reabertos, e a regra antiga contava até o fechamento final, não
  o primeiro. Com a mudança pra "primeira entrada" (item 3 acima), o
  esperado é que essa cauda encolha bastante — falta confirmar com os dados
  reprocessados. Mesmo assim, considerar reportar mediana ao lado da média
  nos indicadores executivos — outliers legítimos (não só reabertura) ainda
  podem existir.
- **Desconto de tempo bloqueado — mantido apesar da dash de referência não
  descontar**: a dash de referência que validou "primeira entrada" (09/2026)
  não desconta bloqueio; decidimos manter o desconto aqui mesmo assim,
  porque é metodologicamente mais correto (não penaliza o time por espera
  externa) e o impacto no número final costuma ser pequeno perto do efeito
  de primeira-vs-última entrada. Se o Cycle Time reprocessado ainda não
  bater com a outra ferramenta, esse é o próximo lugar a olhar.

## Agregação (mês, squad, vertical, empresa)

- Cada work item concluído é agrupado num bucket `(vertical, squad, mês)`
  pelo mês de **conclusão**.
- Dentro de um bucket, cada métrica de tempo é a **média simples** dos itens
  daquele bucket (depois do filtro de ruído). Contagens (Frequência de
  Entrega, Defeitos) são somadas.
- Ao subir de squad → vertical → empresa, as contagens são somadas, mas os
  tempos médios viram **média das médias dos squads**, não ponderada pelo
  volume. Considerar média ponderada se isso distorcer a leitura executiva.
- Itens cujo estado final é categoria `Removed` (cancelados) não entram em
  nenhum cálculo.

## Onde isso está implementado

`extract_tfs_metrics.py`: calendário de feriados e função de horas úteis,
detecção de intervalos de bloqueio (a partir do histórico de `System.Tags` e
`Microsoft.VSTS.CMMI.Blocked`), e o cálculo de Cycle Time (Valor/Issue) e
Lead Time dentro de `build_dataset()`. `mttr_horas` no JSON de saída é hoje
um alias do Cycle Time de Issue em horas.
