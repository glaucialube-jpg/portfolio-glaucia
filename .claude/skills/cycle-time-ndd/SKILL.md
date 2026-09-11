---
name: cycle-time-ndd
description: Calcula Lead Time, Cycle Time, WIP e Espera de work items da NDD (Bug, Issue, User Story, Sprint Task, Spike, Homologation Item) exatamente como o painel oficial "Indicadores Operacionais DevOps" (BIOperacional), incluindo calendário útil por tabela, jornada 08:00-12:00/13:30-17:30, início por LEAST(ActivatedDate, primeiro estado ativo), e desconto de bloqueio por tag/campo. Use quando o usuário pedir cálculo, análise, KPI ou porte (SQL, Power Query, Python) de Lead Time, Cycle Time, WIP ou Espera de work items — especialmente quando o número precisa bater com o BIOperacional.
---

# cycle-time-ndd

## Fonte da verdade

Esta skill replica, **exatamente**, as regras do painel oficial
**Indicadores Operacionais DevOps (BIOperacional)** da NDD. Quando um
número calculado por outra implementação não bater com o painel, a causa
quase sempre é uma destas regras não aplicada — verifique na ordem em que
aparecem abaixo.

Documentação completa (definição, exemplos, casos de exceção):
`docs/DOCUMENTACAO.md`.
Implementação de referência: `reference/ndd_metrics.py`.
Exemplo de configuração: `reference/config.example.json`.
Suíte de testes: `tests/test_ndd_metrics.py`.

## As quatro métricas

- **Lead Time** = `created_date → closed_date`, em dias úteis. Conta a
  fila inteira, não desconta bloqueio nem espera. Ponto de vista de quem
  pediu.
- **Cycle Time** = início do trabalho → `closed_date`, em horas úteis
  (exibido em dias ao dividir por 8), descontando bloqueio. Ponto de
  vista de quem executa.
- **WIP** = início do trabalho → agora. Só existe em item **aberto**.
  Mutuamente exclusivo com Cycle Time — nunca somar os dois.
- **Espera** = dias úteis, dentro da janela do ciclo, em que o item
  esteve em estado não-ativo (fila). Anda ao lado do Cycle Time, não é
  descontada dele.

Não são intercambiáveis, não têm a mesma unidade base, e nunca devem ser
confundidas.

## Regras que não podem ser quebradas

1. **Início do trabalho** = `LEAST(activated_date, primeira entrada real
   em estado ativo)`, ignorando nulos (basta um existir). Nunca usar só
   `ActivatedDate` — cerca de 1 em cada 5 itens fechados não o tem,
   porque muitos vão de `New` direto para `In Development`/`Analysis`/
   `In Test` sem passar por `Active`. "Estado ativo" vem de uma lista
   configurável (hoje 38 estados); estados de espera (`Awaiting Test`,
   `Awaiting Code Review` etc.) não são ativos. Se início **e**
   `closed_date` forem nulos, o item não tem Cycle Time — sai da conta,
   nunca vira zero.

2. **Calendário útil vem de uma tabela**, não de "segunda a sexta"
   calculado na hora (hoje 249 dias úteis em 365 — feriados já
   descontados). Jornada: **08:00-12:00 e 13:30-17:30** (8h úteis/dia).
   Se a tabela oficial de dias úteis estiver disponível, injete-a
   diretamente (`explicit_business_dates`) em vez de recalcular por
   feriados — evita divergência de 1 dia perto de feriados não
   cadastrados aqui.

3. **Fórmula do Cycle Time** (horas úteis):
   ```
   SE closed_date é nulo                -> NULO (é WIP, não Cycle Time)
   SE início é nulo                     -> NULO
   SE início e fechamento no MESMO DIA  -> diferença bruta em horas
   SENÃO -> MAIOR(0,5 ; dias_úteis(início, fechamento] × 8
                       + (hora:min do fechamento − hora:min do início)
                       − horas_bloqueadas)
   ```
   `dias_úteis(início, fechamento]` é **exclusivo no início, inclusivo no
   fim**. O piso de 0,5h evita que um item multi-dia vire zero depois do
   desconto de bloqueio. Mesmo dia é diferença bruta, sem calendário e
   sem bloqueio (a granularidade do bloqueio é o dia). Esta é uma
   **aproximação oficial** — não uma soma exata de intervalos úteis — e
   deve ser reproduzida literalmente, mesmo quando parecer menos precisa
   que um cálculo por interseção de intervalos.

4. **Desconto de bloqueio**: um dia útil dentro da janela do ciclo é
   descontado inteiro (8h) se o item estava bloqueado por tag
   configurável (13 hoje, ex.: `Bloqueado`, `Bloqueado - Ambiente/Infra`)
   **ou** por campo customizado específico de (coleção, projeto) — ex.
   `Ndd.Bloqueio` em `NDD-PrintCollection/nddPrint-360`, `Custom.Bloqueio`
   em `NDD Orbix/Orbix Geral`, ambos com padrão `^Bloqueado`. Vale o
   **histórico** de quando a tag esteve presente, não a tag atual. Dias
   cobertos pelos dois mecanismos contam **uma vez**. O período do campo
   é travado no fechamento: `MENOR(fim_do_bloqueio, closed_date, agora)`
   — sem isso um item fechado com o campo nunca "desbloqueado"
   acumularia bloqueio infinito.

5. **Exclusões e ruído (só para KPIs agregados)**: `config_excluded_cycle_time`
   (hoje vazia) remove itens do Cycle Time só nos KPIs da home e no
   throughput — não nos relatórios detalhados. Além disso, um
   `NULLIF(valor, 0)`: item cujo Cycle Time **arredonda** para zero
   (fechado em segundos, sem ciclo real) é tratado como nulo só para
   médias/KPIs, mas o valor bruto continua existindo nos relatórios
   detalhados.

6. **WIP e Espera não se misturam com Cycle Time**: WIP só existe quando
   `closed_date` é nulo (item aberto); Cycle Time só quando `closed_date`
   existe. Espera é reportada ao lado do Cycle Time, nunca subtraída dele
   — quem tira a fila é o Touch Time (métrica de Eficiência de Fluxo,
   fora do escopo desta skill).

7. **Arredondamento**: por item, 1 casa decimal, **meio para cima**
   (2,35 → 2,4). Em médias, soma em `Decimal` exato antes de dividir —
   nunca em ponto flutuante puro (ponto flutuante faz uma média em `.x5`
   oscilar entre execuções).

8. **Recorte e chaves**:
   - Período filtra por `closed_date` (Lead Time e Cycle Time); o
     Dashboard de Bugs filtra por `created_date`; detalhamento ordena por
     `changed_date`.
   - Tipos considerados por padrão: `Bug`, `Issue`, `User Story`,
     `Sprint Task`, `Spike`, `Homologation Item`. Tipo fora dessa lista
     não entra em indicador nenhum.
   - Time = último segmento do `AreaPath`, aceitando a variação de
     sufixo `" team"` (case-insensitive) como equivalente.
   - **Id de work item não é único entre coleções.** Toda junção e todo
     agrupamento usa a chave composta `(collection, project, id)` — nunca
     agrupar só por `id`.

## Como aplicar

1. Extraia, por work item: `created_date`, `closed_date` (nullable),
   `activated_date` (nullable), histórico real de status
   (`{status, changed_at}`), histórico de tags bloqueantes
   (`{tag, start, end}`, `end=None` se ainda presente), histórico do
   campo customizado de bloqueio (`{value, start, end}`), `collection`,
   `project`, `id`, `area_path`, `work_item_type`.
2. Carregue a configuração (`reference/config.example.json` como ponto de
   partida) com a tabela de calendário real, os 38 estados ativos reais,
   as 13 tags bloqueantes reais, e os campos customizados por
   coleção/projeto.
3. Rode `calculate_metrics(item, config, now)` (ou a lógica equivalente
   portada) e leia:
   - `lead_time_dias_uteis`
   - `cycle_time_horas_uteis`, `cycle_time_dias_uteis`
   - `wip_horas_uteis`, `wip_dias_uteis`
   - `espera_dias_uteis`
   - `data_inicio_trabalho`, `data_fechamento`
   - `excluido_kpi`, `cycle_time_zero_para_kpi`
4. Para médias/KPIs, filtre com `is_valid_for_kpi_average(result)` e some
   com `average_rounded(...)` (Decimal exato) — nunca com `sum()/len()`
   em float puro.

## Pontos que exigiram interpretação (sinalizados para revisão)

O enunciado é preciso na maior parte das regras, mas algumas decisões
ficaram implícitas. Esta implementação assumiu:

1. **"Lead Time em dias úteis corridos"**: interpretado como contagem de
   dias úteis pela mesma tabela de calendário do Cycle Time, na mesma
   convenção exclusivo-início/inclusivo-fim — não como "dias corridos"
   (calendário cheio, incluindo fim de semana). Se "corridos" quiser
   dizer literalmente dias corridos (sem calendário útil) para o Lead
   Time, isso muda a fórmula — revisar com quem mantém o painel se o
   número não bater.
2. **Piso de 0,5h no WIP**: o enunciado define o piso de 0,5h só para a
   fórmula do Cycle Time (regra 4). Apliquei o mesmo piso ao WIP por
   consistência (mesmo calendário, mesmo desconto de bloqueio, mesma
   ideia de "não zerar por bloqueio"), mas o texto original não confirma
   isso explicitamente para WIP.
3. **Cálculo exato da Espera**: o enunciado diz "dias úteis da janela do
   ciclo em que o item esteve em estado não-ativo", sem detalhar a
   granularidade (dia inteiro, como o bloqueio, ou hora exata). Implementei
   por **interseção exata de intervalos** com a jornada útil (mesma lógica
   de `business_hours_in_interval`), não por dia inteiro — porque a Espera
   não tem a mesma ressalva de "granularidade do bloqueio é o dia" que a
   regra 5 dá para bloqueio.
4. **Lista de 38 estados ativos e as 13 tags bloqueantes**: o enunciado dá
   a contagem e exemplos, mas não a lista completa. `config.example.json`
   traz um subconjunto representativo com nota explícita — **precisa ser
   completado com a tabela de configuração real** antes de qualquer
   comparação numérica com o painel.
5. **`normalize_team_name`**: assumido que o sufixo `" team"` é removido
   apenas quando está no final do segmento (case-insensitive), não em
   qualquer posição.

## Teste de aceite (contra produção)

Os testes unitários (`tests/test_ndd_metrics.py`) cobrem cada regra
qualitativa (LEAST, calendário por tabela, fórmula do Cycle Time, piso de
0,5h, bloqueio por tag/campo com união de dias e trava no fechamento,
exclusão de KPI, `NULLIF(0)`, WIP x Cycle Time mutuamente exclusivos,
Espera não descontada, arredondamento meio-para-cima com Decimal, chave
composta, sufixo de time). Eles **não** reproduzem os números de produção
citados no enunciado original (39.000 work items, 24.721 com cycle time
calculável, cycle médio de bugs do nddPrint-360 = 1,93 dias úteis, espera
média = 1,07 dia, ~1.900 itens sem início detectável) porque isso exige a
base real e as listas completas de estados/tags/calendário. Antes de
declarar a implementação "batendo com o painel", rode-a contra uma
extração real dessa base e confira esses cinco números.

## Testes

```
python3 .claude/skills/cycle-time-ndd/tests/test_ndd_metrics.py -v
```
