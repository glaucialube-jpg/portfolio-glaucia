# Flags de qualidade, métricas, indicador executivo, outliers e filtros

## Flags de qualidade do dado

Crie flags para problemas de qualidade e **não as descarte** — elas são insumo
para melhoria de processo:

- `Flag_SemMotivo` — bloqueio identificado, mas nenhum motivo encontrado.
- `Flag_ConcluidoBloqueado` — card concluído, mas sinalização de bloqueio
  permanece aberta.
- `Flag_MotivoSemBloqueio` — existe motivo preenchido, mas não existe
  evidência correspondente de bloqueio.
- `Flag_ConflitoFonte` — diferentes fontes apresentam motivos conflitantes.
- `Flag_PeriodoInvalido` — fim do bloqueio anterior ao início.

## Métricas principais

- **Cards bloqueados atualmente**: quantidade de Work Items não concluídos
  com bloqueio aberto.
- **% de cards que sofreram bloqueio**:
  `Cards únicos que tiveram pelo menos 1 bloqueio / Cards analisados`.
- **Quantidade de eventos de bloqueio**: contagem de períodos/eventos — um
  card pode contribuir com mais de um evento.
- **Tempo médio de bloqueio**: `Soma das durações dos eventos / quantidade de
  eventos`; também permitir análise por card.
- **Principais motivos**: quantidade e percentual de bloqueios por
  `MotivoBloqueio_Normalizado`.
- **Bloqueio por time**: quantidade, percentual, duração média, duração
  total, aging dos bloqueios atuais.
- **Cards bloqueados há mais tempo**: ordenar bloqueios abertos por
  `InicioBloqueio ASC` ou `DuracaoBloqueio DESC`.
- **Cards encerrados com bloqueio aberto**: quantidade de cards concluídos
  cuja sinalização de bloqueio não foi encerrada corretamente.

### Cuidado com duplicidade

Não confunda `Quantidade de cards bloqueados` (cards únicos) com
`Quantidade de eventos de bloqueio` (períodos). Exemplo: card 123 bloqueou 3
vezes → cards únicos bloqueados = 1, eventos de bloqueio = 3. As duas métricas
são válidas, mas respondem perguntas diferentes.

### Denominadores explícitos

Toda métrica percentual deve declarar explicitamente o denominador. Exemplo:
`% cards bloqueados = cards únicos que tiveram bloqueio / cards únicos do
universo analisado`. Não utilize contagem de eventos como numerador desse
indicador. Para `% entregas com bloqueio`, considere apenas os cards
pertencentes ao universo de entrega definido pela análise — não misture
backlog aberto com itens entregues.

## Indicador executivo: Impacto de Bloqueios

Objetivo: tirar a gestão da análise puramente quantitativa e mostrar quanto
os bloqueios impactam o fluxo. Exibir conjuntamente: principais motivos,
quantidade de cards impactados, tempo médio bloqueado, percentual de entregas
que sofreram bloqueio. Quando possível, permitir comparação temporal, por
exemplo:

```
Ago: 18% das entregas sofreram bloqueio | média 3,2 dias
Set: 11% das entregas sofreram bloqueio | média 1,8 dia
```

A intenção é responder: "Estamos bloqueando menos e resolvendo bloqueios mais
rápido?"

## Outliers a priorizar

- **Bloqueios atuais mais antigos**: cards abertos bloqueados há mais tempo.
- **Motivos recorrentes**: motivos com maior frequência.
- **Motivos de maior impacto**: motivos com maior soma de duração.
- **Times com concentração de bloqueios**: percentual anormalmente alto de
  cards bloqueados.
- **Bloqueios repetidos**: mesmo Work Item entrando em bloqueio diversas
  vezes.
- **Bloqueios sem motivo**: bloqueio sinalizado sem causa registrada.
- **Concluídos bloqueados**: cards concluídos que mantêm sinalização de
  bloqueio.

## Filtros esperados nas análises

Período, projeto, collection, time, Product Team, Work Item Type, status,
motivo, categoria do motivo, responsável, bloqueio aberto/encerrado,
concluído/não concluído.
