# Regras temporais e de histórico

## Bloqueio é um evento histórico

Não utilize somente o estado atual do card para responder perguntas como:
quantas vezes ficou bloqueado, quanto tempo ficou bloqueado, quais foram os
principais motivos, quanto tempo os bloqueios impactaram o fluxo. Sempre que
houver histórico/revisões disponível, **reconstrua os períodos**.

Estrutura esperada (mínima):

| WorkItemId | InicioBloqueio | FimBloqueio | Motivo | Fonte |
| --- | --- | --- | --- | --- |

Um mesmo Work Item pode ter **mais de um período de bloqueio**. Exemplo —
card 123: bloqueio 1 (05/08 → 07/08) e bloqueio 2 (12/08 → 15/08). **Não**
consolidar automaticamente como 05/08 → 15/08: são dois eventos distintos.

## Início do bloqueio

O início corresponde à primeira revisão/evento em que o card passa de "não
bloqueado" para "bloqueado". Registre em `InicioBloqueio`. Nunca use
`CreatedDate` como início do bloqueio, exceto se houver evidência histórica de
que o card já nasceu bloqueado.

## Fim do bloqueio

O fim ocorre quando uma revisão/evento muda o card de "bloqueado" para "não
bloqueado". Registre em `FimBloqueio`. Se não existir evento posterior de
desbloqueio: `FimBloqueio = null` e `BloqueioAtual = True`.

## Cards concluídos com bloqueio aberto

Crie regra específica para detectar `Card concluído + BloqueioAtual = True`.
Isso representa uma **inconsistência de processo/dado**, já identificada como
oportunidade de melhoria de governança na NDD. Não interprete esse cenário
automaticamente como um bloqueio que continua acontecendo após a conclusão.
Classifique como `BloqueioEncerradoIncorretamente = True`.

## Estados finais (status concluídos)

Não assuma uma única nomenclatura. Estados finais configurados no projeto
podem incluir, por exemplo: `Resolved`, `Closed`, `Done`, `Concluído`. Antes de
executar cálculos, identifique quais estados são efetivamente considerados
finais no dataset/projeto analisado — isso varia entre projetos/processos.

## Duração do bloqueio

```
DuracaoBloqueio = FimBloqueio - InicioBloqueio
```

Para bloqueios ainda abertos:

```
DuracaoBloqueioAtual = DataReferencia - InicioBloqueio
```

Disponibilize preferencialmente duas medidas:
- duração corrida;
- duração em dias úteis.

Quando usar dias úteis, siga a convenção NDD já utilizada nas métricas de
fluxo: expediente 08:00–17:00, descontar 1 hora de almoço, considerar tabela
de feriados, não contar finais de semana, respeitar início e fim parcial do
expediente. **Não misture** duração corrida e duração útil sem identificar
claramente a unidade nos nomes dos campos (`DuracaoBloqueioHoras`,
`DuracaoBloqueioDiasUteis`).

## Data de referência

Para análises históricas, não use indiscriminadamente `NOW()`. Crie um
parâmetro `DataReferencia`. Para um bloqueio aberto: `FimCalculo =
DataReferencia`. Isso garante reprodutibilidade do dashboard entre execuções.

## Não inventar histórico

Nunca reconstrua um bloqueio anterior à primeira evidência disponível. Se o
histórico começa em determinada data, considere
`HistoricoDisponivelDesde = data da primeira evidência` e não infira
comportamento anterior a ela.

Nas análises atuais da NDD existe um recorte histórico utilizado a partir de
2026 — não inventar dados anteriores ao histórico efetivamente disponível.
Ao trabalhar com revisões: use a primeira revisão real disponível, preserve a
sequência cronológica, não retroaja informação atual e não transforme o
estado atual em histórico fictício. Se houver dúvida, sinalize a limitação
explicitamente ao usuário.
