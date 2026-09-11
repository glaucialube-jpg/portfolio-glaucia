# Campos, fontes de sinalização e fontes de motivo

## Campo padrão de bloqueio

Um dos campos encontrados no ambiente é `Microsoft.VSTS.CMMI.Blocked`. **Não
assumir** que apenas esse campo representa todos os bloqueios existentes na
NDD — considere também as demais fontes de sinalização descritas abaixo.

Ao interpretar `Microsoft.VSTS.CMMI.Blocked`, normalize os valores. Valores
equivalentes a "não bloqueado", quando encontrados: vazio, null, `No`, `Não`,
`False`, `0`. Qualquer valor diferente desses deve ser investigado/tratado
como potencial sinalização de bloqueio.

**Importante:** se os valores literais existentes no ambiente ainda não
tiverem sido validados, não invente uma enumeração oficial. Registre
explicitamente que os valores reais devem ser confirmados no dataset/TFS.

## Fontes de sinalização de bloqueio

Um bloqueio pode aparecer por diferentes mecanismos:

### 1. Campo estruturado
Exemplo: `Microsoft.VSTS.CMMI.Blocked`.

### 2. Tags
Identifique tags relacionadas a bloqueio, por exemplo: `Bloqueado`,
`Bloqueado - motivo`, `Bloqueado – motivo`. Considere variações de
maiúsculas/minúsculas, espaços, hífen `-`, travessão `–` e caracteres
equivalentes — **normalize antes de comparar**.

Exemplo: `Bloqueado – Dependência externa` deve permitir extrair:
- Status lógico: `Bloqueado = Sim`
- Motivo: `Dependência externa`
- Fonte: `Tag`

### 3. Texto / Discussion / histórico
Alguns tipos de Work Item registram informações de bloqueio em Discussion,
comentários ou histórico/revisões. Use esses registros principalmente para
**complementar o motivo**. Não infira automaticamente um período de bloqueio
apenas porque a palavra "bloqueado" apareceu em uma conversa.

## Fontes de motivo do bloqueio (por tipo de Work Item)

Fontes já identificadas na NDD — o nome técnico exato de cada campo deve ser
confirmado no dataset antes de ser tratado como definitivo:

| Tipo de Work Item | Fonte provável do motivo |
| --- | --- |
| OS | `Discussion` |
| Sprint Task / Bug / Issue | campo `Custom.MotivoBloqueio` |
| Spike | `Discussion` |
| PBI | pode existir lista/campo específico — confirmar nome técnico antes de assumir |
| Qualquer tipo | Tags no formato `Bloqueado - <motivo>` |

Exemplo de extração via tag: `Bloqueado - Dependência Produto` → motivo
`Dependência Produto`, fonte `Tag`.

## Precedência das fontes

Quando existirem múltiplas fontes para o mesmo bloqueio, priorize informação
estruturada. Ordem recomendada para o **motivo**:

1. Campo específico de motivo do bloqueio (ex.: `Custom.MotivoBloqueio`).
2. Lista estruturada de motivos (quando existir, ex.: PBI).
3. Tag `Bloqueado - <motivo>`.
4. Discussion/histórico.
5. `"Não informado"`.

**Não sobrescreva informações diferentes silenciosamente.** Quando houver
divergência entre fontes, mantenha campos separados:

- `MotivoBloqueio_Normalizado`
- `MotivoBloqueio_Original`
- `FonteMotivoBloqueio`

Se necessário, registre `ConflitoMotivo = True` (ver também `Flag_ConflitoFonte`
em `metricas-qualidade-outliers.md`).
