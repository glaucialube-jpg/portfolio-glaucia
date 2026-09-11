# Regras de implementação e validação

## Ao gerar Power Query, SQL, Python, OData ou outra transformação

1. Preservar os dados originais.
2. Criar campos normalizados separadamente (nunca sobrescrever o original).
3. Documentar as regras aplicadas.
4. Evitar hardcode quando existir dimensão/tabela de configuração
   (ex.: `Dim_Motivo_Bloqueio`).
5. Tratar `null`.
6. Tratar diferenças de capitalização.
7. Tratar espaços extras.
8. Tratar hífen/travessão (`-` vs `–`) como equivalentes na comparação.
9. Evitar duplicidade por `WorkItemId + evento`.
10. Validar consistência temporal (fim >= início).
11. Priorizar performance.
12. Não consultar repetidamente a mesma fonte quando puder reutilizar uma
    tabela intermediária.

## Validações obrigatórias antes de considerar uma implementação concluída

Apresente ao usuário:

- total de Work Items analisados;
- cards únicos bloqueados;
- eventos de bloqueio;
- bloqueios abertos;
- bloqueios encerrados;
- bloqueios sem motivo;
- cards concluídos ainda marcados como bloqueados;
- conflitos entre fontes;
- períodos inválidos;
- distribuição por fonte do motivo.

Selecione também alguns `WorkItemId`s reais para conferência manual contra o
histórico do TFS.

## Regra de segurança analítica

Se algum campo, tag, valor ou estrutura do TFS não estiver confirmado, **não
invente**. Informe claramente:

> "Este campo/regra precisa ser validado no TFS ou na base antes de ser
> tratado como definitivo."

Isso vale especialmente para: valores literais de
`Microsoft.VSTS.CMMI.Blocked`; campo/lista de motivo do PBI; estados finais
específicos de cada processo; URLs; campos customizados; diferenças entre
projetos/collections.

## Ao entregar código

- Sempre entregar o código **completo**, pronto para copiar e colar — não
  fornecer apenas fragmentos quando a alteração depender de outras etapas da
  consulta.
- Ao alterar uma consulta existente: preservar regras anteriores, informar
  objetivamente o que foi alterado, entregar a versão completa final, evitar
  quebrar nomes de colunas já consumidos por dashboards existentes.
- Antes de remover ou renomear campos, verificar dependências.
