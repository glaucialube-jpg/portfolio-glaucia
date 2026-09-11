# Dataset consolidado: Fato_Bloqueios e dimensões

## Tabela fato

Gere preferencialmente uma tabela fato onde **1 linha = 1 evento/período de
bloqueio**. Nome sugerido: `Fato_Bloqueios`.

Campos mínimos:

- `WorkItemId`
- `Title`
- `WorkItemType`
- `Project`
- `Team`
- `StateAtual`
- `InicioBloqueio`
- `FimBloqueio`
- `BloqueioAtual`
- `DuracaoBloqueioHoras`
- `DuracaoBloqueioDiasUteis`
- `MotivoBloqueio_Original`
- `MotivoBloqueio_Normalizado`
- `FonteMotivoBloqueio`
- `BloqueioEncerradoIncorretamente`
- `AssignedTo`
- `ParentId`
- `URL_TFS`

Campos adicionais, quando disponíveis:

- `Initiative`
- `Feature`
- `Product Team`
- `Area Path`
- `Iteration Path`
- `CreatedDate`
- `ClosedDate`

### Link direto para o TFS

Sempre que o dataset permitir, gere URL clicável para o Work Item no campo
`URL_TFS`, para que gestores saiam do indicador direto para o card que precisa
de ação. **Não invente** o padrão de URL — utilize a URL real/configuração da
collection/projeto fornecida no ambiente.

## Normalização de motivos e Dim_Motivo_Bloqueio

Pequenas variações textuais devem poder ser consolidadas — por exemplo,
`Dependência externa`, `dependencia externa`, `Dependencia Externa`,
`DEPENDÊNCIA EXTERNA` devem resultar em `Dependência externa`. Porém: **não
agrupe motivos semanticamente diferentes** sem uma tabela de mapeamento
explícita.

Prefira criar uma dimensão auditável `Dim_Motivo_Bloqueio` com:

- `MotivoOriginal`
- `MotivoNormalizado`
- `Categoria`
- `Ativo`

Isso torna as regras de normalização auditáveis e evitáveis de hardcode
espalhado pelas consultas.

## Tabelas já conhecidas no ambiente NDD

As bases/tabelas a seguir já são usadas nas análises atuais e podem ser
relevantes, mas **não assuma que todas existem** em qualquer arquivo
analisado — verifique primeiro quais tabelas/consultas realmente estão
disponíveis no material fornecido:

- `Base_Mãe`
- `tb_BASE_MAE`
- `Base_Iniciativas_Atividades`
- `DIM_CARDS_ATUAIS_COMPLETA`
- `BASE_CARDS_RELACIONADOS_ATUAL`
- `Dash_Status_Periodos`
- `Aux_Cards_Deletados`
- `Dash_Cards_Atual`
- `Dim_Status_Dash`
- `Aux_PC_Eventos`
- `Aux_PC_Hierarquia`
- `Dash_Dependencias`
- `Dim_Cards_Atuais`
- `Dash_Bloqueios`
- `Motivos_Por_Fonte`
