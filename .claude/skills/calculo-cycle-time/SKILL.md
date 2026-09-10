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

Fim = ÚLTIMA entrada em `Resolved` OU `Closed`
    (nome literal do estado — não é "categoria Completed" do TFS; em alguns
    templates "Resolved" tem categoria InProgress mas ainda conta como fim
    aqui. Usamos a ÚLTIMA ocorrência, não a primeira, para não contar errado
    quando o item é reaberto e refeito.)

Tempo bloqueado = soma dos intervalos em que, no histórico do item:
    - o campo Microsoft.VSTS.CMMI.Blocked indica bloqueio, OU
    - o campo System.Tags contém alguma destas tags (lista confirmada por
      Gláucia, 09/2026): Bloqueado, #Bloqueado, Bloqueio, Bloqueado -
      Prioridade, Bloqueado - Ambiente/Infra, Bloqueado - Outros Times,
      Bloqueado - Pendência Técnica, "blo", Bloqueada
    Cada intervalo vai do momento em que a condição de bloqueio passou a
    valer até o momento em que deixou de valer (ou até o "Fim" do item, se
    ainda estava bloqueado quando concluiu).

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

## O que ainda precisa de confirmação

1. **Lista de estados "de execução"** — a lista acima (`Active, In
   Development, In Progress, Doing, Em andamento`) foi dada como exemplo
   ("etc."). Pode não cobrir todo tipo/projeto — se um item nunca passar por
   nenhum desses nomes, ele fica sem Cycle Time calculável (mas ainda entra
   no Lead Time). Ampliar a lista conforme surgirem casos.
2. **Campo `Microsoft.VSTS.CMMI.Blocked`** — não confirmamos ainda quais
   valores literais indicam bloqueio nesse campo (ex.: "Yes"/"No",
   "Bloqueado"/vazio). A implementação trata qualquer valor não-vazio e
   diferente de "No"/"Não" como bloqueio — ajustar se isso gerar falso
   positivo/negativo.
3. **"Última entrada em Resolved/Closed"** assume que um item pode reabrir e
   fechar de novo, e que só a última vez importa. Se isso não bater com a
   intuição do time (ex.: preferem a primeira vez que fechou), avisar.

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
