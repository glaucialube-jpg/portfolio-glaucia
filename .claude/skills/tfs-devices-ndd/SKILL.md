---
name: tfs-devices-ndd
description: Conhecimento acumulado sobre como o TFS on-premises da ndd está organizado para a vertical Devices — conexão, projetos, taxonomia de work items, e decisões já tomadas com o time. Use isso antes de escrever qualquer script/consulta contra o TFS da ndd, para não re-descobrir do zero o que já foi validado.
---

# TFS da ndd — organização da vertical Devices

Conhecimento levantado em 09/2026 ao construir o dashboard "Obeya Engenharia"
(Produtividade, Qualidade, Eficiência) e conectar dados reais via
`extract_tfs_metrics.py`. Serve de referência para qualquer integração futura
com esse TFS — evita repetir a descoberta feita por tentativa e erro.

## Conexão

- Servidor: TFS / Azure DevOps Server **on-premises** (não é Azure DevOps Services/nuvem).
- URL da coleção: `https://tfs.ndd.tech/NDD%20Orbix` (nome da coleção é **"NDD Orbix"**, com espaço — precisa URL-encode).
- Autenticação: o servidor **não aceita PAT via Basic Auth** (dá 401) — só funciona com **NTLM** (login de domínio/Windows).
  Usuário no formato UPN funciona: `usuario@ndd.tech`.
  **Nunca commitar senha** — sempre via variável de ambiente/`.env` fora do controle de versão.
- API version testada e funcionando: `6.0`.

## Projetos e verticais

A coleção "NDD Orbix" tem 4 Team Projects: `Orbix`, `Orbix Geral`, `OrbixHL`, `Teste 2`.

Confirmado com a ndd (09/2026):
- **Vertical Devices** = projetos `Orbix` + `Orbix Geral` juntos.
- Fiscal e Logística ainda não têm projeto(s) TFS mapeado(s) — quando conectarem,
  repetir o processo de descoberta abaixo para os projetos correspondentes e
  adicionar uma nova entrada em `TFS_VERTICAL_LABEL`/`TFS_TYPE_MAP_JSON`.

## Taxonomia de work items — varia por projeto

`Orbix` e `Orbix Geral` usam **vocabulários diferentes** para os mesmos conceitos,
mesmo estando na mesma coleção. Não assumir que um nome de tipo é igual entre projetos.

| Conceito | Orbix | Orbix Geral |
|---|---|---|
| "Entrega de valor" (equivalente a User Story) | `PBI` | `User Story` |
| "Descoberta/exploração" (equivalente a Spike) | `Discovery` | `Spike` |
| Defeito em produção | `Issue` | `Issue` |
| Defeito pré-release / downstream (item de Qualidade, não é "defeito em produção") | `Bug` | `Bug` |

**Importante**: `Bug` ≠ defeito em produção. Confirmado com a ndd:
- `Issue` = problema relatado em produção (o que entra em "Defeitos em Produção" / Tempo de Correção do dashboard — **só Issue**, nunca Bug).
- `Bug` = achado em tempo de desenvolvimento/downstream, antes do release. Não conta
  como "defeito em produção", mas **tem indicador próprio no pilar Qualidade**
  (chegou a 1396 "bugs" concluídos num único mês, muito acima do que fazia sentido —
  por isso vale acompanhar como item de Qualidade separado, não misturado com Issue).

### "Itens de Valor" — redefinido em 09/2026: universal, base toda, sem exceção

Decisão revisada por Gláucia em 09/2026 (substitui o mapeamento por projeto acima
*só para fins de Frequência de Entrega/Produtividade* — a tabela acima continua
valendo para "Entrega de valor equivalente a User Story" caso a caso, mas o
recorte de **Produtividade** agora é um conjunto fixo de tipos, aplicado à base
toda, os dois projetos juntos, sem excluir nenhum item que se encaixe:

```
Itens de Valor = Story, User Story, Sprint Task, Spike, PBI
```

Isso **inclui `Sprint Task`**, que a versão anterior desta skill excluía
deliberadamente ("para evitar dupla contagem com User Story/Spike" — ver
histórico). Gláucia confirmou que essa é a definição correta pra Produtividade;
mantenho aqui o alerta que ainda não foi validado com o time: se `Sprint Task`
for, na prática, sub-item/filho de uma `User Story`/`Spike` na hierarquia do
TFS (não confirmado), incluir os dois no mesmo recorte pode contar a mesma
entrega duas vezes. Vale confirmar com o time antes de reportar Frequência de
Entrega como número "fechado" pro executivo. `Story` e `PBI` hoje têm zero
itens concluídos no período observado (Abr–Ago/26) — inclusão é defensiva, sem
efeito prático ainda.

`Orbix Geral` também tem uma quantidade grande de tipos legados/ad-hoc (`Product
Backlog Item UX`, `Product Backlog Item Compliance0`, `Tasks Produto`, etc.) —
continuam fora de "Itens de Valor". Revisar se algum desses deveria entrar,
caso apareçam com volume relevante no futuro.

Para descobrir a taxonomia de um projeto novo (nunca assumir por analogia):
```
py extract_tfs_metrics.py --list-types           # tipos existentes
py extract_tfs_metrics.py --type-counts          # volume real por tipo no período
py extract_tfs_metrics.py --list-states <Tipo>   # estados e suas categorias
```

## "Concluído" e "em andamento" — usar CATEGORIA, não nome do estado

Cada tipo de work item pode ter nomes de estado próprios (ex.: `Bug` usa
`To Do/Approved/Doing/Done`, `PBI` usa `Backlog/Ready/In Progress/Test/Review/
Done/Cancelled`), mas todos mapeiam para categorias padronizadas do TFS:
`Proposed`, `InProgress`, `Resolved`, `Completed`, `Removed`.

A extração detecta "concluído" = última transição para categoria `Completed`,
e "em andamento" = primeira transição para categoria `InProgress`, consultando
`/_apis/wit/workitemtypes/{tipo}/states` por (projeto, tipo). Itens com estado
final de categoria `Removed` (cancelados) não contam como concluídos.

## Squad — resolvido em 09/2026: é o ÚLTIMO nível do Area Path

Não existe campo customizado de Squad/Time no TFS (`Custom.WorkArea` está
sempre vazio nos itens testados) — o squad é inferido do **Area Path**, mas
**não é o primeiro nível após o projeto** (isso era o bug: usar `parts[1]`
fazia quase tudo cair num nó intermediário genérico, "Produtos Geral").

Confirmado cruzando a planilha de referência da ndd (aba `Base_CycleTime`,
coluna `Time`) com `BASE_MAE_TFS.AreaPath` pelo `WorkItemId`: o squad real é
o **último segmento** do Area Path, qualquer que seja a profundidade —
7.906 de 7.912 itens batem (99,9%; os 6 restantes parecem exceções manuais
na planilha, não um padrão diferente). Area Path varia de 1 a 4+ níveis:

| Area Path | Squad (último nível) |
|---|---|
| `Orbix\Printer Management` | Printer Management |
| `Orbix\Platform\Cross Platform` | Cross Platform |
| `Orbix Geral\Produtos Geral\Web Printer Apps` | Web Printer Apps |
| `Orbix Geral\Produtos Geral\Printer Management\Device Metrics` | Device Metrics |
| `Orbix Geral` (sem subpath) | Orbix Geral |

Implementado em `resolve_squad()`: pega o último elemento não-vazio do split
por `\`. Squads reais confirmados na planilha de referência (34 distintos):
Portal, Supply, Printers - Users, Platform, Security Champion, Print
Services, Monitoring, Agents, Thermal, Web Printer Apps, ASM, CS, Printers,
Accounting, Computer Agent, Computer, Produtos Geral, Produto, Printer
Management, Devops, Embedded Printer Apps, Device Metrics, Automated
Services Management, Print Control, GC, Computer Insights, Qualidade,
Automation Devices Management, Core Engineering, entre outros — bem mais
granular do que os ~12 valores vistos antes da correção (que eram, na
maioria, os nós intermediários errados).

## Cuidados de qualidade de dado observados

- MTTR/Cycle Time/Lead Time apareceram bem altos numa primeira extração real
  (dezenas a ~150 dias). Pode ser real (itens realmente represados) ou
  artefato de itens antigos/migrados sendo fechados em lote. Validar com o
  time antes de apresentar esses números como "verdade" para o executivo.
- O MTTR é calculado preferencialmente como `concluído - em_andamento` (tempo
  de trabalho ativo); só cai para `concluído - criado` se o item nunca passou
  por um estado de categoria `InProgress` no histórico.

## Onde está o script de extração

`extract_tfs_metrics.py` (com `.env`, `requirements.txt`, `README.md`) foi
entregue por arquivo na conversa, não vive neste repositório — roda localmente
na máquina da Gláucia (dentro da rede/VPN da ndd) porque este ambiente de
sessão não alcança `tfs.ndd.tech`. Tem modos de descoberta (`--list-fields`,
`--list-types`, `--list-areas`, `--list-states`, `--list-projects`,
`--field-values`, `--type-counts`) — usar esses antes de assumir qualquer
nome de campo/tipo/estado num projeto novo.
