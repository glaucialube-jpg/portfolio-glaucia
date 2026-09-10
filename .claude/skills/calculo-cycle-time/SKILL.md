---
name: calculo-cycle-time
description: Regras e fórmulas de cálculo de Cycle Time, Lead Time, MTTR e Frequência de Entrega usadas no dashboard "Obeya Engenharia" (Produtividade/Qualidade/Eficiência). Use isso antes de calcular, alterar ou explicar qualquer uma dessas métricas, para manter a definição consistente entre o protótipo, o script de extração e qualquer relatório derivado.
---

# Cálculo de Cycle Time e métricas relacionadas

Definições fixadas ao construir o dashboard "Obeya Engenharia" e o script
`extract_tfs_metrics.py`. Cycle Time não se calcula isolado — ele compartilha
a mesma detecção de estado (categoria) com Lead Time e MTTR, então as quatro
métricas estão documentadas juntas.

## Definições (origem: quadro Obeya da ndd, replicadas no Miro)

- **Cycle Time** — "Eficiência do time. Tempo que o time leva para entregar a
  demanda desde o momento em que começou a trabalhar nela." Menor é melhor.
- **Lead Time** — "Data conclusão − Data criação." Mede o tempo total desde
  que o item existe até ser entregue (inclui tempo parado no backlog).
- **MTTR (defeitos)** — tempo médio de resposta/resolução de um defeito.
- **Frequência de Entrega** — quantidade de itens de "entrega de valor"
  concluídos por período (proxy de Deployment Frequency quando não há dado
  de deploy real).

## Fórmulas implementadas

Dado um work item com histórico de transições de estado:

```
done_at         = última transição para um estado de categoria "Completed"
in_progress_at  = primeira transição para um estado de categoria "InProgress"
created_at      = data de criação do item (System.CreatedDate)

lead_time_dias  = (done_at - created_at)               em dias corridos
cycle_time_dias = (done_at - in_progress_at)            em dias corridos, só se in_progress_at existir
mttr_horas      = (done_at - (in_progress_at ou created_at)) em horas
                  # usa in_progress_at quando existe (tempo de trabalho ativo);
                  # cai para created_at só se o item nunca teve uma transição
                  # de categoria InProgress no histórico.
```

Por que categoria e não nome de estado: nomes de estado variam por tipo de
work item e por projeto (ver skill `tfs-devices-ndd`), mas a categoria
(`Proposed/InProgress/Resolved/Completed/Removed`) é padronizada pelo TFS.
Isso evita ter que manter uma lista de nomes de estado por tipo/projeto.

## PENDENTE — descontos no tempo bruto (apontado por Gláucia em 09/2026)

A fórmula acima usa o tempo corrido "cru" entre duas datas. Isso **infla**
Cycle Time, Lead Time e MTTR sempre que o item ficou parado por um motivo que
não deveria contar como "trabalho em andamento". Ainda não implementado —
precisa definir com o time antes de calcular:

1. **Tempo de bloqueio/impedimento** — existe algum estado (ex. "Blocked",
   "Impedido") ou campo (`Microsoft.VSTS.CMMI.Blocked` apareceu na lista de
   campos do Orbix) que marca isso? Se sim, subtrair o tempo nesse estado do
   Cycle/Lead Time do item.
2. **Tags de espera** — ex. "aguardando terceiro", "aguardando cliente".
   Precisamos saber quais tags a ndd usa pra isso e se elas têm data de
   início/fim rastreável (via `/updates`, como fazemos pra estado) ou só o
   nome da tag (sem tempo associado, o que dificultaria descontar).
3. **Fins de semana e feriados** — hoje é tudo em dias corridos. Se o pedido
   for dias úteis, precisa de um calendário de feriados da ndd (nacionais +
   locais, se houver) pra excluir da contagem, não só sáb/dom.

Enquanto isso não for resolvido, todo número de Cycle Time/Lead Time/MTTR no
dashboard deve vir acompanhado de um aviso de que é uma **média** e de que
esses descontos ainda não foram aplicados (o dashboard já faz isso na aba
"Racional dos Indicadores" e nos cards de Eficiência/Qualidade).

Itens cujo estado final é categoria `Removed` (cancelados) **não** entram no
cálculo — não são "concluídos".

## Unidade e granularidade

- Todos os tempos são em **dias/horas corridos**, não dias úteis. Isso é uma
  simplificação conhecida — se o negócio pedir dias úteis, precisa subtrair
  fins de semana (e feriados, se relevante) no cálculo do delta.
- Um item sem `in_progress_at` fica com `cycle_time_dias = null` (não faz
  sentido estimar) — ele ainda entra no Lead Time normalmente.

## Agregação (mês, squad, vertical, empresa)

- Cada work item concluído é agrupado em um bucket `(vertical, squad, mês)`
  pelo mês de **conclusão** (`done_at`), não de criação.
- Dentro de um bucket, cada métrica de tempo (`lead_time_dias`,
  `cycle_time_dias`, `mttr_horas`) é a **média simples** dos itens daquele
  bucket. `frequencia_entrega` e `defeitos_producao` são contagens (soma).
- Ao subir de squad → vertical → empresa, as contagens são **somadas**, mas
  os tempos médios são recalculados como **média das médias dos squads**,
  não uma média ponderada pelo volume de cada squad.
  **Limitação conhecida**: se um squad grande (muitos itens) tiver um cycle
  time bem diferente de um squad pequeno, a média da vertical fica distorcida
  para o lado do squad pequeno. Se isso importar para a leitura executiva,
  trocar por média ponderada pelo número de itens antes de exibir.

## Onde isso está implementado

Em `extract_tfs_metrics.py`: função `done_and_in_progress_at()` (detecção via
categoria), `build_dataset()` (fórmulas de lead/cycle/MTTR por item) e
`summarize()`/`avg()` (agregação por bucket e rollup). Qualquer mudança nessas
regras deve ser replicada nas três funções juntas — elas assumem a mesma
definição de "concluído"/"em andamento".
