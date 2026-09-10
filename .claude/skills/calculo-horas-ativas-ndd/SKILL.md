---
name: calculo-horas-ativas-ndd
description: Calcula Horas Ativas de um item/card da ndd a partir do histórico de tags e do campo de bloqueio, descontando períodos efetivamente bloqueados dentro da jornada elegível. Use sempre que precisar calcular, auditar ou explicar quantas horas um item ficou realmente ativo (não bloqueado) — inclusive como base para Cycle Time. Determinística e conservadora: nunca infere bloqueio sem evidência temporal explícita, nunca amplia a lista oficial de tags bloqueantes por semelhança de texto.
---

# Cálculo de Horas Ativas ndd

Skill de referência para calcular quantas horas um item/card da ndd ficou
**efetivamente ativo** — ou seja, dentro da jornada de trabalho elegível e
**fora** de qualquer período em que uma tag ou campo de bloqueio oficial
estava vigente. É o princípio por trás do Cycle Time (skill
`calculo-cycle-time`): Cycle Time = Horas Ativas ÷ 8, convertido em dias
úteis. Esta skill documenta a regra em si, independente de estar sendo
aplicada via script (`extract_tfs_metrics.py`) ou manualmente, item por
item, a partir dos dados brutos de tags/histórico que alguém colar na
conversa.

**Princípio fundamental:**

```
HORAS ATIVAS = HORAS ELEGÍVEIS − HORAS BLOQUEADAS
```

Todo período efetivamente bloqueado é removido do cálculo. Nada além disso.

## Regra de ouro: não inferir sem evidência

Esta skill é **determinística e conservadora**. Isso significa:

- Uma tag só bloqueia se estiver **literalmente** na lista oficial (seção
  seguinte) — nunca por semelhança de nome, palavra-chave ou "parece que".
- Um bloqueio só desconta o intervalo em que **está comprovadamente
  vigente** — nunca o histórico inteiro do item só porque a tag existe hoje.
- Se a vigência de uma tag bloqueante não puder ser determinada pelos dados
  disponíveis, a skill **não inventa** datas — ela relata a lacuna e, se
  necessário para concluir o cálculo, pede o dado que falta.
- Status do item, texto descritivo, ou tags "parecidas" **nunca** substituem
  a lista oficial nem a vigência temporal real.

## 1. Lista oficial de tags bloqueantes

Comparação **case-insensitive**, após: (1) remover espaços nas pontas, (2)
normalizar maiúsculas/minúsculas, (3) preservar hífens, `#` e `/` como estão.

```
Bloqueado
Bloqueio
Bloqueado - Ambiente/Infra
Bloqueado - Prioridade
Bloqueado - Outros Times
Bloqueado - Pendência Técnica
Bloqueada
#Bloqueado
blo
```

`"Bloqueado"`, `"BLOQUEADO"` e `"bloqueado"` são a mesma tag e todas
bloqueiam. Fora isso, **nenhuma outra variação é aceita automaticamente** —
mesmo que pareça claramente relacionada.

### Tags que NÃO bloqueiam (mesmo parecendo)

Exemplos reais já identificados na interface da ndd que **não** entram na
lista oficial e, portanto, **não bloqueiam**, mesmo contendo palavras
parecidas com "bloqueio":

```
Blocante
SLA - Blocante
CNTIPO:BLOQUEAR USUÁRIO
Ag. Publicação
Ag. Publicação v1.2.14
Aguardando publicação
Publicação 10/06/26, 28/05/26, 03/06/26, 22/06/26, 06/07/26, 13/08/26, 15/07/26, 18/05/26
Publicado
Sem publicação
Solução de problema
Cliente: Ministério Público do Estado do Rio ...
BLACKECCO
Enabler
PrinterMonitorUsbLinux
Product Backlog Items 2861: [Contabilização]...
```

Datas de publicação, em particular, **nunca** disparam bloqueio por si só —
mesmo que pareçam indicar um item "esperando" algo.

**Se uma tag nova aparecer e não estiver em nenhuma das duas listas**:
trate como **não bloqueante** por padrão (regra de ouro), e sinalize a
dúvida para quem pediu o cálculo em vez de decidir sozinha.

## 2. Fontes de bloqueio e como combiná-las

Um item pode estar bloqueado por duas fontes independentes:

1. **Tag bloqueante** (lista acima) presente no campo de tags do item.
2. **Campo de bloqueio dedicado** do item (ex.: `Microsoft.VSTS.CMMI.Blocked`
   no TFS), quando existir e seu valor indicar bloqueio (ex.: `"Yes"` —
   comparação exata, case-insensitive; confirmar o valor literal usado no
   sistema de origem antes de assumir).

As duas fontes são combinadas com **OU**: o item só volta a ficar
"desbloqueado" quando **nenhuma das duas condições** vale mais. Se a tag for
removida antes do campo (ou vice-versa), o bloqueio continua até a segunda
remoção. Nunca feche um intervalo de bloqueio porque uma única fonte parou
de indicar bloqueio, se a outra ainda indica.

## 3. Intervalos: união, não soma

Bloqueio é tratado como **intervalo de tempo** `[início, fim)`, nunca como
contagem de ocorrências.

**Múltiplas tags bloqueantes simultâneas não multiplicam o desconto.** Se
`Bloqueado`, `Bloqueado - Prioridade` e `Bloqueado - Ambiente/Infra`
estiverem todas vigentes das 10:00 às 14:00, o desconto é **4 horas**, nunca
4+4+4=12.

**Intervalos sobrepostos se unem:**
```
Bloqueio 1: 10:00 → 12:00
Bloqueio 2: 11:00 → 14:00
Resultado:  10:00 → 14:00  (4h bloqueadas, não 3h+3h)
```

**Intervalos consecutivos (fim de um = início do outro) também se unem:**
```
10:00 → 12:00
12:00 → 15:00
Resultado: 10:00 → 15:00
```

## 4. Bloqueio parcial, total e ausente

- **Parcial**: desconta só a parcela bloqueada dentro do período elegível.
  Ex.: elegível 08:00–18:00 (10h), bloqueio 13:00–15:00 (2h) → ativas = 8h.
- **Dia inteiro bloqueado**: se a tag cobre todo o período elegível do dia,
  horas ativas daquele dia = 0.
- **Sem tag bloqueante vigente**: não desconta nada — mesmo que o item
  tenha outras tags (não-bloqueantes) ou esteja num status como "Em
  andamento", "Ag. Publicação", "Publicado", "Aguardando publicação". Status
  e texto descritivo **nunca** inferem bloqueio sozinhos.

## 5. Jornada elegível e calendário

Quando parâmetros de calendário/jornada forem fornecidos (ou já estiverem
definidos em contexto, como no dashboard "Dash Engenharia" — 08:00–17:00,
−1h de almoço, sem fim de semana, calendário de feriados 2026 da ndd — ver
skill `calculo-cycle-time`), respeite-os: hora fora da jornada elegível
nunca conta como ativa, e nunca é descontada como "bloqueio" — ela
simplesmente já não fazia parte das horas elegíveis. Bloqueio e "fora da
jornada" são conceitos distintos; não confundir os dois nem descontar a
mesma hora duas vezes.

Se nenhum calendário/jornada for fornecido para uma análise pontual, pergunte
antes de assumir um padrão — não adote silenciosamente 24h/dia nem invente
um horário comercial genérico sem confirmar.

## 6. Ordem de processamento

1. Identificar o período total de análise (início/fim do cálculo).
2. Identificar as horas elegíveis dentro desse período (jornada × calendário).
3. Ler todas as tags associadas ao item, com suas datas de entrada/saída.
4. Ler o campo de bloqueio dedicado (se existir), com suas datas de mudança.
5. Normalizar as tags (trim, case-insensitive, preservando `-`, `#`, `/`).
6. Comparar cada tag com a lista oficial de tags bloqueantes (seção 1) —
   nunca por similaridade.
7. Para cada tag bloqueante e para o campo de bloqueio, determinar a
   vigência temporal (quando passou a valer, quando deixou de valer).
8. Combinar as duas fontes com OU (seção 2) e transformar em intervalos.
9. Unificar intervalos sobrepostos ou consecutivos (seção 3).
10. Limitar os intervalos de bloqueio ao período elegível (não descontar
    bloqueio que caiu fora da jornada/calendário).
11. Calcular horas bloqueadas = soma dos intervalos finais.
12. Calcular `Horas Ativas = Horas Elegíveis − Horas Bloqueadas`.
13. Apresentar a memória de cálculo completa (seção 8).

## 7. Quando a vigência não pode ser determinada

Se existir uma tag bloqueante mas os dados disponíveis não permitem
determinar quando ela começou e/ou terminou:

- **Não invente** datas, horários ou uma vigência aproximada.
- Relate explicitamente: qual tag, que há evidência de bloqueio, e que a
  vigência não pôde ser determinada com os dados fornecidos.
- Se a vigência for indispensável para fechar o número final, **peça** o
  dado que falta (ex.: "preciso do histórico de quando a tag X foi
  adicionada/removida") em vez de estimar ou assumir "provavelmente o dia
  todo" / "provavelmente desde a criação".
- Se for possível calcular um número parcial (ex.: horas ativas até o
  momento em que a lacuna começa), apresente esse número parcial com a
  ressalva explícita, em vez de recusar o cálculo inteiro.

## 8. Formato de saída — sempre mostrar a memória de cálculo

Nunca devolver só o número final quando houver dado suficiente para
explicar. Formato padrão:

```
Período analisado: 01/09/2026 → 10/09/2026
Horas elegíveis: 72h

Tags bloqueantes identificadas:
- Bloqueado
- Bloqueado - Ambiente/Infra

Períodos bloqueados (já unificados):
- 02/09 10:00 → 02/09 18:00 = 8h
- 05/09 09:00 → 06/09 12:00 = 15h

Total bloqueado: 23h

Horas ativas: 72h − 23h = 49h

Justificativa: os dois períodos foram descontados porque havia tag
bloqueante da lista oficial vigente nesses intervalos, dentro da jornada
elegível. Nenhuma outra tag do item (ex.: "Ag. Publicação") gerou desconto.
```

Se algo ficou incerto (seção 7), inclua uma linha "Observações" descrevendo
exatamente a lacuna, sem deixar isso implícito no número.

## 9. Exemplos de entrada e saída

**Exemplo A — bloqueio parcial dentro de um dia**
- Entrada: jornada elegível 08:00–18:00 (10h); tag `Bloqueado` vigente
  13:00–15:00.
- Saída: Horas elegíveis 10h; bloqueadas 2h; **ativas 8h**.

**Exemplo B — múltiplas tags simultâneas (sem duplicar)**
- Entrada: `Bloqueado` (10:00–14:00), `Bloqueado - Prioridade` (10:00–14:00),
  `Bloqueado - Ambiente/Infra` (10:00–14:00).
- Saída: os três intervalos são idênticos → união = 10:00–14:00 →
  **bloqueadas 4h** (não 12h).

**Exemplo C — tags sobrepostas parcialmente**
- Entrada: `Bloqueado` 10:00–12:00; `Bloqueio` 11:00–14:00.
- Saída: união = 10:00–14:00 → **bloqueadas 4h** (não 3h+3h=6h).

**Exemplo D — tag não-oficial não bloqueia**
- Entrada: item só tem a tag `Ag. Publicação`.
- Saída: nenhuma tag bloqueante encontrada → **bloqueadas 0h** → ativas =
  elegíveis.

**Exemplo E — bloqueio de dia inteiro**
- Entrada: jornada elegível do dia = 8h; `Bloqueada` vigente o dia inteiro.
- Saída: **ativas do dia = 0h**.

**Exemplo F — vigência desconhecida**
- Entrada: item tem a tag `blo`, mas não há data de quando foi adicionada
  nem removida nos dados fornecidos.
- Saída: "Há evidência de bloqueio (tag `blo`), mas a vigência não pôde ser
  determinada com os dados disponíveis — preciso do histórico de mudança
  dessa tag pra descontar o período corretamente. Não descontei nada até
  confirmar."

**Exemplo G — status não é bloqueio**
- Entrada: item no status "Aguardando publicação", sem nenhuma tag da lista
  oficial.
- Saída: **bloqueadas 0h** — status não substitui tag.

## 10. Prioridade das regras em caso de conflito

1. Dados temporais explícitos (datas/horas reais de início e fim).
2. Vigência real da tag/campo (quando passou a valer, quando parou).
3. Lista oficial de tags bloqueantes (seção 1) — nunca ampliada por
   semelhança.
4. Jornada/calendário elegível.
5. Status do item.
6. Texto descritivo/título do item.

Itens 5 e 6 **nunca** sobrepõem uma regra explícita de vigência de bloqueio
definida pelos itens 1–4.

## 11. O que nunca fazer

- Descontar o mesmo período de tempo duas vezes.
- Somar horas bloqueadas pela quantidade de tags em vez de unificar
  intervalos.
- Descontar um dia inteiro quando o bloqueio foi só parcial.
- Descontar como bloqueio um período que já estava fora da jornada elegível.
- Assumir que uma tag presente hoje existiu durante todo o histórico do
  item.
- Classificar uma tag nova como bloqueante por parecer semelhante às da
  lista oficial (ex.: "Blocante", "SLA - Blocante",
  "CNTIPO:BLOQUEAR USUÁRIO") — isso exige autorização explícita de quem
  mantém a lista oficial antes de ser adicionada.
- Inventar datas, horários ou vigências quando a informação não existir.

## Relação com outras skills

- `calculo-cycle-time`: aplica esta mesma lógica de bloqueio dentro do
  cálculo de Cycle Time/Lead Time/MTTR do dashboard "Dash Engenharia",
  convertendo Horas Ativas em dias úteis (`÷8`) e combinando com início/fim
  de execução. O código de referência está em
  `extract_tfs_metrics.py` (funções `compute_blocked_intervals` e
  `net_business_days`).
- `tfs-devices-ndd`: contexto de onde essas tags e o campo de bloqueio
  (`Microsoft.VSTS.CMMI.Blocked`) vêm no TFS da ndd.
