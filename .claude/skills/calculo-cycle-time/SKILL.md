---
name: calculo-cycle-time
description: Calcula Lead Time e Cycle Time exatamente como o painel oficial "Indicadores Operacionais DevOps" (BIOperacional) da NDD — substitui a especificação anterior baseada no dashboard "Obeya Engenharia". Use isso antes de calcular, alterar ou explicar Lead Time, Cycle Time, WIP ou Espera, para manter a definição consistente entre o script de extração, o painel e qualquer relatório derivado.
---

# Cálculo de Lead Time e Cycle Time (fonte: painel BIOperacional)

Substitui integralmente a especificação anterior desta skill (baseada no
dashboard "Obeya Engenharia" — MTTR, Frequência de Entrega, calendário de
feriados 2026 local). A fonte da verdade agora é o painel oficial
**Indicadores Operacionais DevOps (BIOperacional)**. As regras abaixo são
essa fonte da verdade. Quando um número não bater com o painel, a causa
quase sempre é uma destas regras não aplicada, na ordem em que aparecem.

## 1. As duas métricas são diferentes

**Lead Time** = `created_date → closed_date`, em dias úteis. Conta a fila
inteira, não desconta bloqueio nem espera. É o tempo do ponto de vista de
quem pediu.

**Cycle Time** = início do trabalho → `closed_date`, em horas úteis,
descontando bloqueio. É o tempo do ponto de vista de quem executa.

Não são intercambiáveis e não têm a mesma unidade base. Cycle Time é
calculado em horas e dividido por 8 quando exibido em dias.

## 2. Início do trabalho (a regra que mais gera divergência)

O início não é simplesmente o `ActivatedDate` do TFS. É:

```
inicio = LEAST(activated_date, primeiro_periodo_em_estado_ativo)
```

O menor dos dois, e `LEAST` ignora nulo: basta um existir. Motivo: cerca
de 1 em cada 5 itens fechados não tem `ActivatedDate`, porque o TFS só
carimba esse campo quando o item passa por `Active`, e muito item vai de
`New` direto para `In Development`, `Analysis` ou `In Test`. Usar só o
campo descarta esses itens do cálculo.

"Estado ativo" vem de uma tabela de configuração
(`config_active_hours_states`), hoje com 38 estados marcados como ativos.
Estados de espera (`Awaiting Test`, `Awaiting Code Review`,
`Awaiting Analysis`, `Awaiting Review`, `Ready for Dev`) não são ativos.

Se início e `closed_date` forem nulos, o item **não tem** cycle time e
sai da conta. Não vira zero.

## 3. Calendário

`dias_úteis` vem de uma tabela de calendário, não de uma regra de
"segunda a sexta". Hoje: 249 dias úteis em 365, ou seja, feriados já
estão descontados.

Jornada: **08:00-12:00 e 13:30-17:30**, que é o dia útil de 8 horas usado
na conversão.

## 4. Fórmula do Cycle Time

```
SE closed_date é nulo           -> NULO (item aberto não tem cycle time, tem WIP)
SE início é nulo                -> NULO
SE início e fechamento no MESMO DIA -> diferença bruta em horas (epoch / 3600)
SENÃO                           -> MAIOR(0,5 ;
                                     dias_úteis(início, fechamento] × 8
                                   + (hora:min do fechamento − hora:min do início)
                                   − horas_bloqueadas)
```

Três detalhes que costumam faltar:

- A contagem de dias úteis é **exclusiva no início e inclusiva no fim**:
  `> data_início AND <= data_fechamento`.
- O piso de 0,5 hora existe para item multi-dia não virar zero depois do
  desconto de bloqueio.
- Mesmo dia é diferença bruta, sem calendário e sem desconto de
  bloqueio, porque a granularidade do bloqueio é o dia.

## 5. Desconto de bloqueio

Um dia útil dentro da janela do ciclo é descontado inteiro (8 horas) se
naquele dia o item estava bloqueado por qualquer um dos dois mecanismos:

**Tag bloqueante** — lista configurável. Confirmado na tela de
configuração de produção ("Tags Bloqueantes (Horas)"), hoje **9 tags**
marcadas, de um universo de 4.469 tags distintas usadas na base:

| Tag | Ocorrências |
|---|---|
| `Bloqueado` | 1.796 |
| `#Bloqueado` | 32 |
| `Bloqueio` | 24 |
| `Bloqueada` | 16 |
| `Bloqueado - Ambiente/Infra` | 12 |
| `Bloqueado - Prioridade` | 11 |
| `Bloqueado - Outros Times` | 4 |
| `Bloqueado - Pendência Técnica` | 4 |
| `bloque` | 1 |

**A comparação é sensível a maiúsculas/minúsculas (case-sensitive), com
correspondência exata da tag** — não um "contém" nem uma normalização por
`casefold`. Prova disso na própria tela: `bloqueado` em minúsculas (726
ocorrências — mais frequente que várias das marcadas!) está **desmarcada**
e não conta como bloqueio, assim como `CNTIPO:BLOQUEAR USUÁRIO`,
`BlockedPostAttackSecurity`, `#Bloqueada` e `Blocante`. Não amplie essa
lista por semelhança textual (ex.: não tratar `Bloqueada` e `#Bloqueada`
como equivalentes) — só as 9 tags marcadas acima contam, exatamente como
grafadas.

Vale o **histórico** de quando a tag esteve presente, não a tag atual do
item.

**Campo customizado de bloqueio**, por coleção e projeto:

| coleção / projeto | campo | padrão |
|---|---|---|
| `NDD-PrintCollection` / `nddPrint-360` | `Ndd.Bloqueio` | `^Bloqueado` |
| `NDD Orbix` / `Orbix Geral` | `Custom.Bloqueio` | `^Bloqueado` |

Dois cuidados:

- O desconto conta **dias distintos**. Dia coberto pela tag e pelo campo
  é descontado uma vez, não duas.
- O período do campo tem trava no fechamento:
  `MENOR(fim_do_bloqueio, closed_date, agora)`. Sem isso, item fechado
  com o campo nunca zerado acumularia bloqueio infinito.

## 6. Exclusões

Existe uma lista de itens excluídos do cycle time
(`config_excluded_cycle_time`), hoje vazia. Quando usada, vale só nos
KPIs da home e no throughput, não nos relatórios detalhados. São duas
variantes da mesma métrica.

Nos KPIs há ainda um `NULLIF(valor, 0)`: item cujo cycle time arredonda
para zero é tratado como nulo e sai da média. São itens fechados em
segundos, sem ciclo real.

## 7. Métricas irmãs, para não confundir

**WIP** = início do trabalho → agora, mesmo calendário e mesmo desconto
de bloqueio. Só existe em item aberto. Cycle Time e WIP são mutuamente
exclusivos: um dos dois é sempre nulo. Nunca somar os dois na mesma
estatística.

**Espera** = dias úteis da janela do ciclo em que o item esteve em
estado não marcado como ativo (fila). Anda ao lado do cycle time, não é
descontada dele. Cycle time é tempo decorrido, fila inclusa; quem tira a
fila é o Touch Time da Eficiência de Fluxo.

## 8. Arredondamento e média

Por item: arredonda para 1 casa decimal.

Na média: converte para decimal exato antes de somar (`DECIMAL(18,1)`),
não soma em ponto flutuante. Em ponto flutuante uma média que cai em
`.x5` sai como `2,3499999` e arredonda para baixo, oscilando entre
execuções.

O arredondamento é meio para cima: exatos `2,35` viram `2,4`.

## 9. Recorte e filtros

- O período filtra por `closed_date` em Lead Time e Cycle Time. O
  Dashboard de Bugs filtra por `created_date`, e a tabela de
  detalhamento ordena por `changed_date`.
- Tipos considerados por padrão: `Bug`, `Issue`, `User Story`,
  `Sprint Task`, `Spike`, `Homologation Item`. Tipo não ativado não
  entra em indicador nenhum.
- Time é resolvido pelo último segmento do `AreaPath`, com uma variação
  aceita: o sufixo `" team"`.
- Id de work item é único **por coleção**, não globalmente. Hoje há
  1.347 ids repetidos entre coleções. Toda junção e todo agrupamento usa
  a chave completa `(collection, project, id)`. Agrupar só por `id` faz
  um item herdar dado de outro, sem erro nenhum.

## 10. Teste de aceite

Se a implementação estiver certa, ela reproduz estes números da base de
produção:

- 39.000 work items, 24.721 com cycle time calculável.
- Bugs do `nddPrint-360`, cycle médio: 1,93 dias úteis.
- Espera média dos bugs do `nddPrint-360`: 1,07 dia, ou seja mais da
  metade do ciclo é fila.
- Itens fechados sem nenhum início detectável: cerca de 1.900, e eles
  não entram em nenhuma média.

Se o número der **menor** que o oficial, suspeite primeiro de: início
usando só `ActivatedDate` (perde 20% dos itens), ou espera sendo
descontada do ciclo.

Se der **maior**, suspeite de: bloqueio não descontado (inclusive
comparação de tag case-insensitive quando deveria ser exata), ou dias
corridos no lugar de dias úteis.

## Onde isso está implementado

Ver a skill `cycle-time-ndd` para uma implementação de referência
executável (Python, testável) desta mesma especificação, incluindo Lead
Time, Cycle Time, WIP e Espera. Se este repositório também mantiver
`extract_tfs_metrics.py` (ou equivalente) para o painel BIOperacional, a
lógica de calendário útil, detecção de bloqueio (tag + campo
customizado, comparação case-sensitive) e a fórmula do Cycle Time devem
seguir literalmente as regras acima.
