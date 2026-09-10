# Documentação — Skill cycle-time-ndd

## 1. Objetivo

Padronizar o cálculo do **Cycle Time** de work items da NDD, de forma
reaproveitável em análises, scripts, Power Query, Python, SQL ou qualquer
outra implementação futura, sem depender de uma ferramenta específica de
rastreamento (Azure DevOps, Jira etc.).

## 2. Definição do indicador

**Cycle Time** é o tempo útil decorrido entre:

- a **primeira** entrada real do card em um status equivalente a
  "trabalho em execução"; e
- sua **conclusão** (primeira entrada em um status final que ocorre
  depois do início encontrado).

A data de **criação** do card nunca é usada como início do Cycle Time.

O resultado é expresso em **dias úteis**:

```
CycleTimeDiasUteis = CycleTimeHorasUteis / 8
```

## 3. Regras

### 3.1 Status de início (configurável)

Padrão: `Active`, `In Development`, `In Progress`, `Doing`, `Em andamento`.

### 3.2 Status de fim (configurável)

Padrão: `Resolved`, `Closed`.

### 3.3 Calendário útil

- Dias úteis: segunda a sexta-feira (configurável).
- Horário útil: 08:00 às 17:00.
- Almoço descontado: 1 hora (padrão 12:00-13:00, configurável).
- Total: 8 horas úteis por dia.
- Não contam: sábados, domingos, feriados (lista configurável, recebida
  como parâmetro ou fonte externa).

### 3.4 Ruído

Resultados com `CycleTimeDiasUteis <= 0,01` são marcados como inválidos
para fins de agregação (`CycleTimeValido = false`,
`MotivoInvalidacao = "Cycle Time <= 0,01 dia útil"`). O valor numérico
ainda é calculado e retornado, apenas não deve entrar em médias/indicadores.

### 3.5 Tipos de indicador (configurável)

- **Cycle Time de Valor**: `Sprint Task`, `User Story`, `Spike`.
- **Cycle Time de Issue**: `Issue`.

Work item types fora dessas listas retornam `TipoCycleTime = null`, mas o
cálculo de tempo continua normalmente (a classificação é só um rótulo).

### 3.6 Histórico real

O cálculo usa exclusivamente o histórico real de mudança de status do
work item — nunca datas inventadas ou interpoladas. O início é a primeira
mudança real para um status de execução.

Se o item:
- nunca entrou em status de execução;
- não foi concluído; ou
- tem histórico ausente/insuficiente,

o resultado é **nulo/não calculável**, nunca zero (ver `MotivoInvalidacao`).

### 3.7 Transições: início inclusivo, fim exclusivo

O tempo passa a contar no instante exato em que o card entra no status de
execução, e para de contar no instante exato em que entra no status
final.

### 3.8 Múltiplas entradas em execução

Por padrão, usa-se a **primeira** entrada real em status de execução como
início. Movimentações posteriores (sair e voltar para execução) não
reiniciam o relógio. Uma implementação futura pode definir outra regra
explicitamente — a regra padrão não deve ser alterada silenciosamente.

## 4. Parâmetros de configuração

Ver `reference/config.example.json`. Resumo:

| Parâmetro | Descrição | Default |
|---|---|---|
| `calendar.work_start` / `work_end` | Janela de expediente | 08:00 / 17:00 |
| `calendar.lunch_start` / `lunch_end` | Janela de almoço descontada | 12:00 / 13:00 |
| `calendar.business_weekdays` | Dias úteis da semana | seg-sex |
| `calendar.holidays` | Lista de feriados (datas) | vazia — deve ser fornecida |
| `statuses.execution_statuses` | Status que iniciam o Cycle Time | Active, In Development, In Progress, Doing, Em andamento |
| `statuses.final_statuses` | Status que encerram o Cycle Time | Resolved, Closed |
| `types.value_types` | Tipos classificados como "Valor" | Sprint Task, User Story, Spike |
| `types.issue_types` | Tipos classificados como "Issue" | Issue |
| `min_valid_business_days` | Limiar de ruído (dias úteis) | 0.01 |

## 5. Saídas

| Campo | Tipo | Descrição |
|---|---|---|
| `CycleTimeHorasUteis` | float / nulo | Horas úteis entre início e fim |
| `CycleTimeDiasUteis` | float / nulo | `CycleTimeHorasUteis / 8` |
| `DataInicioCycleTime` | datetime / nulo | Instante da primeira entrada em execução |
| `DataFimCycleTime` | datetime / nulo | Instante da 1ª entrada em status final (Resolved/Closed) **após** `DataInicioCycleTime` |
| `TipoCycleTime` | "Valor" \| "Issue" \| nulo | Classificação do indicador |
| `CycleTimeValido` | bool | Se o resultado pode entrar em agregações |
| `MotivoInvalidacao` | string / nulo | Motivo quando `CycleTimeValido = false` |

Valores possíveis de `MotivoInvalidacao`:
- `Sem status de execução`
- `Item não concluído`
- `Histórico insuficiente`
- `Cycle Time <= 0,01 dia útil`

## 6. Exemplos de entrada e saída

### Exemplo 1 — mesmo dia

Entrada (histórico):
```
New          2024-01-08 08:00
In Progress  2024-01-08 09:00
Resolved     2024-01-08 11:00
```
Saída:
```
CycleTimeHorasUteis = 2.0
CycleTimeDiasUteis  = 0.25
DataInicioCycleTime = 2024-01-08 09:00
DataFimCycleTime    = 2024-01-08 11:00
TipoCycleTime       = Valor (se work_item_type = Sprint Task)
CycleTimeValido     = true
MotivoInvalidacao   = null
```

### Exemplo 2 — atravessando fim de semana

Entrada:
```
In Progress  2024-01-05 09:00   (sexta)
Closed       2024-01-08 10:00   (segunda)
```
Saída:
```
CycleTimeHorasUteis = 9.0   # 7h na sexta + 2h na segunda; sáb/dom não contam
CycleTimeDiasUteis  = 1.125
CycleTimeValido     = true
```

### Exemplo 3 — item ainda aberto

Entrada:
```
In Progress  2024-01-08 08:00
```
Saída:
```
CycleTimeHorasUteis = null
CycleTimeDiasUteis  = null
DataInicioCycleTime = 2024-01-08 08:00
DataFimCycleTime    = null
CycleTimeValido     = false
MotivoInvalidacao   = "Item não concluído"
```

### Exemplo 4 — sem status de execução

Entrada:
```
New       2024-01-08 08:00
Resolved  2024-01-08 11:00
```
Saída:
```
CycleTimeValido   = false
MotivoInvalidacao = "Sem status de execução"
```

### Exemplo 5 — ruído (Cycle Time muito pequeno)

Entrada:
```
Doing   2024-01-08 08:00
Closed  2024-01-08 08:02
```
Saída:
```
CycleTimeHorasUteis = 0.033...
CycleTimeDiasUteis  = 0.0041...
CycleTimeValido     = false
MotivoInvalidacao   = "Cycle Time <= 0,01 dia útil"
```
(o valor é calculado e retornado, mas não deve entrar em médias)

## 7. Casos de exceção

- **Histórico ausente ou vazio** → `Histórico insuficiente`.
- **Nenhuma entrada em status de execução** → `Sem status de execução`.
- **Entrou em execução mas nunca chegou a um status final** →
  `Item não concluído`.
- **Cycle Time calculado, porém <= 0,01 dia útil** →
  `Cycle Time <= 0,01 dia útil` (valor retornado, mas inválido p/ agregação).
- **Tipo de work item fora das listas configuradas** → `TipoCycleTime = null`,
  cálculo de tempo segue normalmente.

## 8. Instruções de uso

1. Extraia o histórico real de status do work item na ferramenta de
   origem (ex.: Azure DevOps Boards, Jira) — uma lista ordenável de
   `{status, timestamp}`.
2. Prepare a configuração (feriados do ano corrente, status equivalentes
   do board em uso, tipos de work item) a partir de
   `reference/config.example.json`.
3. Chame `calculate_cycle_time(history, work_item_type, config)` (Python,
   `reference/cycle_time.py`) ou porte o mesmo algoritmo para a
   linguagem/ferramenta de destino (SQL, Power Query, etc.), reproduzindo
   fielmente:
   - a busca da primeira entrada em status de execução;
   - a busca da primeira entrada em status final após esse ponto;
   - o cálculo de horas úteis por interseção de intervalos, dia a dia;
   - as regras de invalidação e o limiar de ruído.
4. Ao agregar (médias, percentis, indicadores por sprint/período), filtre
   sempre por `CycleTimeValido = true`.
5. Rode a suíte de testes (`tests/test_cycle_time.py`) sempre que a
   configuração de status/feriados/calendário for alterada, para garantir
   que os casos obrigatórios continuam corretos.
