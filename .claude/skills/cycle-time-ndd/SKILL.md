---
name: cycle-time-ndd
description: Calcula o Cycle Time de work items da NDD (Sprint Task, User Story, Spike, Issue) a partir do histórico real de status, usando calendário útil (seg-sex, 08:00-17:00, menos 1h de almoço, sem feriados). Use quando o usuário pedir cálculo, análise ou indicador de Cycle Time, lead time até conclusão, ou tempo em execução de work items — em Python, SQL, Power Query ou qualquer outra implementação.
---

# cycle-time-ndd

## Objetivo

Calcular o **Cycle Time** de work items da NDD de forma padronizada e
reaproveitável em análises ad hoc, scripts, Power Query, Python, SQL ou
qualquer implementação futura. Esta skill é a fonte única da verdade sobre
a regra de negócio — qualquer porte para outra linguagem deve reproduzir
exatamente o algoritmo descrito aqui.

Documentação completa (definição, exemplos de entrada/saída, casos de
exceção): `docs/DOCUMENTACAO.md`.
Implementação de referência, testável e comentada: `reference/cycle_time.py`.
Exemplo de arquivo de configuração: `reference/config.example.json`.
Suíte de testes obrigatória: `tests/test_cycle_time.py`.

## Definição do indicador

Cycle Time = tempo útil decorrido entre:

1. a **primeira** entrada real do card em um status de execução, e
2. a entrada em um status final que ocorre depois disso,

expresso em **dias úteis** (horas úteis / 8). **Nunca** usar a data de
criação do card como início.

## Quando usar

- O usuário pede para calcular/analisar Cycle Time de work items da NDD.
- É preciso implementar essa métrica em uma nova linguagem/ferramenta
  (Power Query, SQL, outro script Python) — porte o algoritmo de
  `reference/cycle_time.py`, não reinvente as regras.
- É preciso validar se uma implementação existente de Cycle Time está de
  acordo com a regra padronizada da NDD.

## Como aplicar

1. Obtenha o **histórico real de mudança de status** do work item (lista
   de transições `{status, timestamp}`, em ordem cronológica ou não — a
   implementação ordena). Nunca infira ou interpole datas intermediárias.
2. Carregue a configuração (`reference/config.example.json` como ponto de
   partida) com: status de execução, status finais, feriados, tipos de
   work item por indicador, e o calendário útil.
3. Rode `calculate_cycle_time(history, work_item_type, config)` (ou a
   lógica equivalente portada) e leia o resultado:
   - `CycleTimeHorasUteis`, `CycleTimeDiasUteis`
   - `DataInicioCycleTime`, `DataFimCycleTime`
   - `TipoCycleTime` ("Valor" ou "Issue", conforme `types` na config)
   - `CycleTimeValido` (bool)
   - `MotivoInvalidacao`, quando `CycleTimeValido` for `false`
4. **Nunca** inclua itens com `CycleTimeValido = false` em médias ou
   indicadores agregados — mesmo que um valor numérico tenha sido
   calculado (caso do ruído `<= 0,01` dia útil).

## Regras que não podem ser quebradas

- Início = primeira entrada real em status de execução. Reentradas
  posteriores em status de execução **não** reiniciam o relógio.
- Fim = primeira entrada em status final que ocorre **depois** do início
  encontrado.
- Início inclusivo, fim exclusivo.
- Calendário: seg-sex, 08:00-17:00, menos 1h de almoço (12:00-13:00 por
  padrão, configurável) = 8h úteis/dia. Sábados, domingos e feriados
  (lista configurável) não contam.
- Resultado com `dias_uteis <= 0.01` é marcado inválido para fins de
  agregação (`MotivoInvalidacao = "Cycle Time <= 0,01 dia útil"`), mas o
  valor calculado ainda é retornado.
- Item sem status de execução no histórico, sem conclusão, ou com
  histórico ausente/vazio → resultado **nulo/não calculável**, nunca
  zero. Ver `MotivoInvalidacao` para distinguir os três casos.
- Todas as listas (status de execução, status finais, feriados, tipos de
  work item por indicador) são configuráveis — nunca hardcode uma lista
  diferente da fornecida pela configuração ativa.

## Pontos que exigiram interpretação (sinalizados para revisão)

Os requisitos originais definiram a maior parte da regra com precisão,
mas deixaram algumas decisões implícitas. Esta implementação assumiu:

1. **Horário do almoço**: o enunciado diz "descontar 1 hora de almoço"
   sem especificar o horário. Assumido 12:00-13:00 (compatível com o
   total de 8h úteis/dia a partir de 08:00-17:00). Configurável via
   `lunch_start`/`lunch_end`.
2. **Qual entrada em status final conta como fim**: quando há múltiplas
   entradas em status final (ex.: reabertura após "Closed"), esta versão
   usa a **primeira** entrada em status final após o início do Cycle
   Time. Reaberturas subsequentes não são tratadas nesta versão — ficou
   fora do escopo pedido (que só especifica a regra para múltiplas
   entradas em status de **execução**, não em status final). Uma
   implementação futura pode adicionar uma regra explícita para isso.
3. **Distinção entre "Sem status de execução" e "Histórico
   insuficiente"**: interpretado como: histórico ausente/vazio →
   "Histórico insuficiente"; histórico presente mas sem nenhuma entrada
   em status de execução → "Sem status de execução".
4. **Normalização de nomes de status/tipos**: comparações de status e de
   tipo de work item ignoram maiúsculas/minúsculas e espaços nas pontas,
   para tolerar pequenas variações de cadastro sem exigir listas
   duplicadas na configuração.

## Testes

Rode a suíte obrigatória (sem dependências externas):

```
python3 .claude/skills/cycle-time-ndd/tests/test_cycle_time.py -v
```

Cobre: mesmo dia, atravessar fim de semana, atravessar feriado, início
antes/depois do expediente, fim fora do expediente, sem status de
execução, item ainda aberto, ruído (`<= 0,01`), múltiplas entradas em
execução, histórico ausente e tipo de work item não mapeado.
