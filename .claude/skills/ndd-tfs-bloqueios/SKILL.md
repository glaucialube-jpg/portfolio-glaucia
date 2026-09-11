---
name: ndd-tfs-bloqueios
description: Referência oficial da NDD para qualquer análise, transformação, consulta, dashboard ou cálculo envolvendo bloqueios de Work Items no TFS/Azure DevOps Server (especialmente vertical Devices). Use sempre que o pedido envolver "bloqueio", "bloqueado", "Blocked", tempo bloqueado, motivos de bloqueio, Fato_Bloqueios, Dash_Bloqueios, ou métricas de impacto de bloqueio em Power Query/SQL/Python/Power BI/Looker Studio/Excel sobre dados de TFS/ADO da NDD.
---

# Tratamento de Bloqueios — TFS/ADO NDD

Esta Skill existe para impedir que as regras de bloqueio sejam reinventadas a cada
nova análise. Sempre que uma tarefa envolver bloqueios de Work Items no
TFS/Azure DevOps Server da NDD, aplique este conhecimento antes de escrever
qualquer consulta, fórmula ou código.

## Princípio fundamental: três conceitos, nunca misturados

1. **Sinalização** — o card está/esteve bloqueado? (campo, tag, texto)
2. **Motivo** — por que foi bloqueado? (pode vir de fonte diferente da sinalização)
3. **Período** — quando começou, quando terminou, quanto tempo durou?

Nunca tratar essas três coisas como um único dado. Um card pode ter sinalização
sem motivo, motivo sem sinalização correspondente, ou múltiplos períodos de
bloqueio distintos que não devem ser consolidados em um só.

## Fluxo de trabalho obrigatório

Antes de aplicar qualquer regra, identifique no material fornecido pelo usuário:

1. Qual é a fonte disponível (Excel, OData, export do TFS, tabela já tratada)?
2. Quais campos realmente existem no dataset (não assumir por nome parecido)?
3. Existe histórico/revisões disponível, ou apenas o estado atual?
4. Quais mecanismos de bloqueio aparecem (campo estruturado, tag, texto)?
5. Quais fontes de motivo existem para os tipos de Work Item envolvidos?
6. Qual é o universo de Work Items a analisar (projeto, time, período, tipo)?

Se houver ambiguidade relevante nessas seis perguntas, **pergunte ao usuário antes
de assumir**. Se não houver ambiguidade, execute diretamente.

Nunca invente: valores literais de campos, nomes de campos customizados, estados
finais de workflow, ou padrões de URL do TFS. Quando algo não estiver confirmado
no dataset/ambiente, diga explicitamente:
> "Este campo/regra precisa ser validado no TFS ou na base antes de ser tratado como definitivo."

## Referências detalhadas (carregar conforme a tarefa)

- `references/campos-fontes-motivo.md` — campo `Microsoft.VSTS.CMMI.Blocked` e sua
  normalização; fontes de sinalização (campo, tag, texto/discussion); fontes de
  motivo por tipo de Work Item (OS, Sprint Task/Bug/Issue, Spike, PBI, Tags);
  ordem de precedência entre fontes e regra de não sobrescrever silenciosamente.
- `references/regras-temporais.md` — bloqueio como evento histórico (múltiplos
  períodos por card); regra de início e fim de bloqueio; cards concluídos com
  bloqueio aberto (`BloqueioEncerradoIncorretamente`); estados finais não são
  universais; cálculo de duração (corrida vs. dias úteis, convenção NDD);
  `DataReferencia` para reprodutibilidade; regra de não inventar histórico
  anterior à primeira evidência disponível (recorte histórico NDD desde 2026).
- `references/dataset-fato-bloqueios.md` — schema da tabela fato
  `Fato_Bloqueios` (1 linha = 1 evento de bloqueio), campos mínimos e opcionais;
  normalização de motivos e dimensão `Dim_Motivo_Bloqueio` auditável; tabelas já
  conhecidas no ambiente NDD (verificar existência antes de usar).
- `references/metricas-qualidade-outliers.md` — flags de qualidade de dado
  (`Flag_SemMotivo`, `Flag_ConcluidoBloqueado`, `Flag_MotivoSemBloqueio`,
  `Flag_ConflitoFonte`, `Flag_PeriodoInvalido`); métricas principais (cards
  bloqueados, % de cards com bloqueio, eventos vs. cards únicos, tempo médio,
  principais motivos, análise por time); indicador executivo "Impacto de
  Bloqueios" com comparação temporal; outliers a priorizar; regra de
  denominadores explícitos em todo percentual; filtros esperados nas análises.
- `references/implementacao-validacao.md` — regras ao gerar Power Query/SQL/
  Python/OData (preservar dados originais, tratar null/capitalização/hífen,
  evitar duplicidade, performance); checklist de validações obrigatórias antes
  de considerar uma implementação concluída; regra de segurança analítica
  (nunca inventar campos/valores não confirmados); regra de entrega de código
  completo e não quebrar colunas já consumidas por dashboards existentes.

## Filosofia da análise

O objetivo nunca é apenas responder "quantos cards estão bloqueados?". A análise
deve ajudar a responder: o que está bloqueando os times, quais causas são
recorrentes, quanto tempo isso custa, onde estão os maiores gargalos, quais
bloqueios precisam de ação agora, quais problemas são sistêmicos, e se a
frequência/duração dos bloqueios e a qualidade do registro estão melhorando ao
longo do tempo. O resultado deve apontar para ação de melhoria contínua, não
apenas para um número em um dashboard.
