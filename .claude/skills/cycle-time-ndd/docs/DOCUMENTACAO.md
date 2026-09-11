# Documentação — Skill cycle-time-ndd (fonte: painel BIOperacional)

## 1. Objetivo

Reproduzir, sem ambiguidade e de forma reaproveitável (Python, SQL, Power
Query ou qualquer outra linguagem), as regras de **Lead Time**, **Cycle
Time**, **WIP** e **Espera** do painel oficial "Indicadores Operacionais
DevOps" (BIOperacional) da NDD. Este documento — junto com
`reference/ndd_metrics.py` — é a fonte da verdade: qualquer porte deve
reproduzir cada regra abaixo literalmente, mesmo quando ela parecer uma
aproximação em vez de um cálculo "matematicamente exato".

## 2. Definição das quatro métricas

| Métrica | Janela | Unidade base | Desconta bloqueio? | Existe quando |
|---|---|---|---|---|
| Lead Time | `created_date → closed_date` | dias úteis | Não | item fechado |
| Cycle Time | início do trabalho → `closed_date` | horas úteis (/8 = dias) | Sim | item fechado |
| WIP | início do trabalho → agora | horas úteis (/8 = dias) | Sim | item aberto |
| Espera | dentro da janela do Cycle Time, tempo em estado não-ativo | dias úteis | — (é ela mesma "fila") | item fechado com início e fim conhecidos |

Lead Time é o ponto de vista de quem pediu (fila inteira). Cycle Time é o
ponto de vista de quem executa (só o tempo de trabalho, sem contar antes
do início). WIP é o Cycle Time de um item ainda aberto. Espera mede
quanto do Cycle Time foi fila, sem alterá-lo.

## 3. Regras

### 3.1 Início do trabalho

```
inicio = LEAST(activated_date, primeira_entrada_em_estado_ativo)
```

`LEAST` ignora nulo — basta um dos dois valores existir. Motivo: no TFS,
`ActivatedDate` só é carimbado quando o item passa pelo estado `Active`;
muitos itens vão de `New` direto para `In Development`, `Analysis` ou
`In Test`, sem nunca passar por `Active`. Usar só o campo descarta ~20%
dos itens fechados do cálculo.

"Estado ativo" vem de uma tabela de configuração
(`config_active_hours_states`, hoje 38 estados). Estados de espera
(`Awaiting Test`, `Awaiting Code Review`, `Awaiting Analysis`,
`Awaiting Review`, `Ready for Dev`) não são ativos.

Se início **e** `closed_date` forem nulos, o item **não tem** Cycle
Time — sai da conta, nunca vira zero.

### 3.2 Calendário

Dias úteis vêm de uma **tabela de calendário**, não de uma regra fixa de
"segunda a sexta". Hoje: 249 dias úteis em 365 (feriados já descontados
na própria tabela).

Jornada: **08:00-12:00 e 13:30-17:30** — 8 horas úteis por dia (já sem
almoço, porque o intervalo 12:00-13:30 simplesmente não faz parte da
jornada).

### 3.3 Fórmula do Cycle Time

```
SE closed_date é nulo                -> NULO  (item aberto tem WIP, não Cycle Time)
SE início é nulo                     -> NULO
SE início e fechamento no MESMO DIA  -> diferença bruta em horas (epoch/3600)
SENÃO -> MAIOR(0,5 ;
               dias_úteis(início, fechamento] × 8
             + (hora:min do fechamento − hora:min do início)
             − horas_bloqueadas)
```

Detalhes que costumam faltar em reimplementações:

- `dias_úteis(início, fechamento]` é **exclusivo no início, inclusivo no
  fim** (`> data_início AND <= data_fechamento`).
- O piso de **0,5 hora** existe para um item multi-dia não virar zero
  depois do desconto de bloqueio.
- "Mesmo dia" é diferença bruta, **sem** calendário e **sem** desconto de
  bloqueio, porque a granularidade do desconto de bloqueio é o dia — não
  faz sentido descontar um "dia inteiro" de bloqueio dentro de um cálculo
  que já é sub-diário.
- Esta fórmula é uma **aproximação**, não uma soma exata de interseções
  de intervalo (compare com a Espera, que usa interseção exata). Ela deve
  ser reproduzida assim mesmo — divergir "para ficar mais exato" quebra a
  paridade com o painel.

### 3.4 Desconto de bloqueio

Um dia útil dentro da janela do ciclo é descontado inteiro (8h) se, nesse
dia, o item estava bloqueado por qualquer um dos dois mecanismos:

- **Tag bloqueante**: lista configurável (hoje 13 tags: `Bloqueado`,
  `Bloqueada`, `#Bloqueado`, `Bloqueado - Ambiente/Infra`,
  `Bloqueado - Definição`, `Bloqueado - Outros Times`,
  `Bloqueado - Pendência Técnica`, `Bloqueado - Prioridade`, entre
  outras). Vale o **histórico** de quando a tag esteve presente, não a
  tag atual do item.
- **Campo customizado de bloqueio**, por coleção/projeto:

  | coleção / projeto | campo | padrão |
  |---|---|---|
  | `NDD-PrintCollection` / `nddPrint-360` | `Ndd.Bloqueio` | `^Bloqueado` |
  | `NDD Orbix` / `Orbix Geral` | `Custom.Bloqueio` | `^Bloqueado` |

Dois cuidados:

1. O desconto conta **dias distintos** — um dia coberto pela tag e pelo
   campo ao mesmo tempo é descontado uma vez, não duas.
2. O período do campo tem trava no fechamento:
   `MENOR(fim_do_bloqueio, closed_date, agora)`. Sem isso, um item
   fechado com o campo nunca "desbloqueado" acumularia bloqueio infinito.

### 3.5 Exclusões

`config_excluded_cycle_time` (hoje vazia) remove itens do Cycle Time —
mas só nos KPIs da home e no throughput, **não** nos relatórios
detalhados. Duas variantes da mesma métrica coexistem: uma "crua" (todos
os itens calculáveis) e uma "para KPI" (crua menos exclusões menos
ruído).

Adicionalmente, nos KPIs há um `NULLIF(valor, 0)`: um item cujo Cycle
Time **arredonda** para zero é tratado como nulo e sai da média — são
itens fechados em segundos, sem ciclo real.

### 3.6 WIP e Espera

- **WIP** = início do trabalho → agora, mesmo calendário e mesmo
  desconto de bloqueio do Cycle Time. Só existe em item aberto. Cycle
  Time e WIP são **mutuamente exclusivos**: um dos dois é sempre nulo.
  Nunca somar os dois na mesma estatística.
- **Espera** = dias úteis, dentro da janela do ciclo, em que o item
  esteve em estado **não** marcado como ativo (fila). Anda ao lado do
  Cycle Time, **não é descontada dele**. Cycle Time é tempo decorrido,
  fila inclusa; quem tira a fila é o Touch Time da Eficiência de Fluxo
  (fora do escopo desta skill).

### 3.7 Arredondamento e média

- Por item: arredonda para 1 casa decimal.
- Na média: converte para decimal exato antes de somar
  (equivalente a `DECIMAL(18,1)`), nunca soma em ponto flutuante — em
  ponto flutuante, uma média que cai exatamente em `.x5` pode virar
  `2,3499999...` e arredondar para baixo, oscilando entre execuções.
- O arredondamento é **meio para cima**: `2,35` vira `2,4`.

### 3.8 Recorte e filtros

- O período filtra por `closed_date` em Lead Time e Cycle Time. O
  Dashboard de Bugs filtra por `created_date`. A tabela de detalhamento
  ordena por `changed_date`.
- Tipos considerados por padrão: `Bug`, `Issue`, `User Story`,
  `Sprint Task`, `Spike`, `Homologation Item`. Tipo não ativado não entra
  em indicador nenhum.
- Time é resolvido pelo último segmento do `AreaPath`, com uma variação
  aceita: o sufixo `" team"`.
- Id de work item é único **por coleção**, não globalmente — hoje há
  ~1.347 ids repetidos entre coleções na base de produção. Toda junção e
  todo agrupamento usa a chave completa `(collection, project, id)`.
  Agrupar só por `id` faz um item herdar dado de outro, sem erro nenhum
  (silenciosamente).

## 4. Parâmetros de configuração

Ver `reference/config.example.json`. Resumo:

| Parâmetro | Descrição | Default/exemplo |
|---|---|---|
| `calendar.business_weekdays` / `holidays` | Base para o calendário útil quando a tabela oficial não está disponível | seg-sex, lista de feriados |
| `calendar.explicit_business_dates` | Lista exata de dias úteis, se a tabela oficial estiver disponível — bate 1:1 | não usado por padrão |
| `calendar.journey_blocks` | Jornada útil (blocos manhã/tarde) | 08:00-12:00, 13:30-17:30 |
| `active_states` | Estados considerados "em execução" | 38 estados (representativo aqui) |
| `wait_states` | Estados de fila explícitos | Awaiting Test, Awaiting Code Review, ... |
| `blocking.tags` | Tags que bloqueiam o item | 13 tags (representativo aqui) |
| `blocking.custom_fields` | Campo de bloqueio por (coleção, projeto) | `Ndd.Bloqueio`, `Custom.Bloqueio` |
| `accepted_types` | Tipos de work item considerados | Bug, Issue, User Story, Sprint Task, Spike, Homologation Item |
| `excluded_cycle_time` | Chaves `(collection, project, id)` excluídas dos KPIs | vazia |
| `min_cycle_time_hours` | Piso da fórmula do Cycle Time | 0,5 |
| `rounding_decimals` | Casas decimais no arredondamento | 1 |

## 5. Saídas

| Campo | Tipo | Descrição |
|---|---|---|
| `lead_time_dias_uteis` | float / nulo | `created_date → closed_date`, dias úteis |
| `cycle_time_horas_uteis` | float / nulo | Fórmula da seção 3.3 |
| `cycle_time_dias_uteis` | float / nulo | `cycle_time_horas_uteis / 8` |
| `wip_horas_uteis` / `wip_dias_uteis` | float / nulo | Só quando `closed_date` é nulo |
| `espera_dias_uteis` | float / nulo | Fila dentro da janela do ciclo |
| `data_inicio_trabalho` | datetime / nulo | `LEAST(activated_date, primeira entrada ativa)` |
| `data_fechamento` | datetime / nulo | `closed_date` |
| `excluido_kpi` | bool | Item está em `config_excluded_cycle_time` |
| `cycle_time_zero_para_kpi` | bool | Cycle Time arredonda para 0 (regra `NULLIF`) |

Use `is_valid_for_kpi_average(result)` para filtrar antes de agregações,
e `average_rounded(valores)` para a média em Decimal exato.

## 6. Exemplos de entrada e saída

### Exemplo 1 — item sem ActivatedDate, direto para In Test

Entrada:
```
created_date   = 2024-01-08 08:00
activated_date = null
status_history = [New@08:00, In Test@2024-01-09 10:00]
closed_date    = 2024-01-09 15:00
```
Saída:
```
data_inicio_trabalho = 2024-01-09 10:00   # LEAST ignora o nulo
cycle_time_horas_uteis = 5.0              # mesmo dia -> diferença bruta
```

### Exemplo 2 — multi-dia sem bloqueio

Entrada: início segunda 09:00, fechamento terça 15:00.
Saída:
```
cycle_time_horas_uteis = 14.0
# dias_uteis(seg,ter] = 1 dia -> 8h; + (15:00 - 09:00) = 6h -> 14h
```

### Exemplo 3 — com bloqueio

Entrada: início segunda 08:00, fechamento quarta 08:00, bloqueado o dia
inteiro de terça (tag e/ou campo).
Saída:
```
cycle_time_horas_uteis = 8.0
# dias_uteis(seg,qua] = {ter, qua} = 2 dias -> 16h; delta hora = 0h; -8h bloqueado = 8h
```

### Exemplo 4 — item ainda aberto

Saída:
```
cycle_time_dias_uteis = null
wip_dias_uteis        = <calculado até agora>
```

### Exemplo 5 — sem início detectável

Saída:
```
data_inicio_trabalho  = null
cycle_time_dias_uteis = null   # nunca zero
```

### Exemplo 6 — Cycle Time arredonda para zero

Entrada: início e fechamento com 1 segundo de diferença.
Saída:
```
cycle_time_horas_uteis   = 0.000278
cycle_time_zero_para_kpi = true   # sai da média, mas o valor bruto existe
```

## 7. Casos de exceção

- **Início e fechamento nulos** → sem Cycle Time, item fora da conta.
- **`closed_date` nulo** → item aberto, só WIP.
- **Início nulo, `closed_date` presente** → sem Cycle Time (item fechado
  sem início detectável — na base oficial, ~1.900 itens).
- **Cycle Time arredonda para zero** → fora das médias/KPIs, mas presente
  nos relatórios detalhados.
- **Item na lista de exclusão** → fora das médias/KPIs e do throughput,
  presente nos relatórios detalhados.
- **Campo de bloqueio nunca "desbloqueado"** → travado no fechamento
  (`MENOR(fim, closed_date, agora)`), não acumula bloqueio infinito.

## 8. Instruções de uso

1. Extraia do TFS/Azure DevOps: `created_date`, `closed_date`,
   `activated_date`, histórico real de status, histórico de tags,
   histórico do campo customizado de bloqueio, `collection`, `project`,
   `id`, `area_path`, `work_item_type`.
2. Complete `reference/config.example.json` com a tabela real de
   calendário, os 38 estados ativos reais, as 13 tags bloqueantes reais e
   os campos customizados reais — os valores no exemplo são
   representativos, não a lista de produção.
3. Chame `calculate_metrics(item, config, now)` (Python,
   `reference/ndd_metrics.py`) ou porte fielmente para SQL/Power Query,
   reproduzindo a ordem exata: início por `LEAST`, fórmula do Cycle Time
   (com o caso "mesmo dia" tratado à parte), desconto de bloqueio por
   união de dias com trava no fechamento, WIP só quando aberto, Espera
   por interseção com a jornada útil.
4. Ao agregar, filtre com `is_valid_for_kpi_average` e some em Decimal
   exato (`average_rounded`), nunca em ponto flutuante puro.
5. Antes de declarar a implementação "batendo com o painel", valide
   contra os cinco números de aceite citados na fonte original
   (39.000 work items, 24.721 com cycle time calculável; cycle médio de
   bugs do `nddPrint-360` = 1,93 dias úteis; espera média dos mesmos
   bugs = 1,07 dia; ~1.900 itens fechados sem início detectável). Se o
   número sair **menor** que o oficial, suspeite primeiro de: início
   usando só `ActivatedDate` (perde ~20% dos itens), ou espera sendo
   descontada do ciclo por engano. Se sair **maior**, suspeite de:
   bloqueio não descontado, ou dias corridos no lugar de dias úteis.
6. Rode `tests/test_ndd_metrics.py` sempre que a configuração de
   estados/tags/calendário mudar.
