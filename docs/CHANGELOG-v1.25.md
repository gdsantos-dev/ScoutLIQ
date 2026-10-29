# ScoutLIQ 1.25.0 — Visual Polish geral

## Objetivo
Quinto ciclo pós-redesign da v1.20.0. A v1.24.0 permanece como baseline funcional e este release fecha o roadmap mobile com uma passada visual geral em desktop e celular, sem alterar regras do produto.

## Shell e navegação
- Fundo passa a ser liso e neutro, removendo o glow crimson residual da aplicação.
- Masthead e navegação perdem divisórias redundantes e ganham hierarquia por espaço, contraste e tipografia.
- O seletor Operar/Gerir fica mais silencioso e a bolinha decorativa do ambiente é removida do markup.
- Crimson fica reservado principalmente para seleção, ação primária, alerta e intenção real.
- Navegação inferior mobile mantém o estado ativo legível sem colorir ícones desnecessariamente.

## Tipografia e ritmo
- Títulos de página passam a depender menos de linhas inferiores e mais de respiro vertical.
- Peso, escala e tracking são ajustados para leitura mais editorial.
- Labels ficam mais próximos dos campos e textos auxiliares perdem peso visual.
- Spacing de formulários, cabeçalhos e ações é normalizado entre módulos.

## Controles e formulários
- Botões, inputs, selects e date picker usam raios e alturas mais consistentes.
- Foco continua acessível, mas com halo mais curto e funcional.
- Menus, popovers, command bar e dialogs usam superfícies sólidas; blur/glass decorativo é removido.
- Tabs e filtros ficam menos parecidos com cards aninhados.

## Tabelas, listas e workspaces
- Hairlines passam a usar contraste menor para reduzir a sensação de grade.
- Tabelas ganham cabeçalho mais discreto, linhas mais leves e hover quase imperceptível.
- Negociações, oportunidades, automações, campanhas e buscas salvas recebem o mesmo tratamento de interação e divisórias.
- Badges ficam menos arredondadas e mais utilitárias.

## Estados vazios e carregamento
- Estados vazios viram blocos editoriais alinhados ao conteúdo, sem caixa tracejada ou grande área ociosa.
- Skeletons usam raio e superfície coerentes com o restante do produto.

## Mobile
- Masthead e bottom navigation passam a superfícies sólidas sem glass decorativo.
- Densidade de listas e workspaces é refinada sem reduzir alvos de toque.
- Sheets e editor de automações mantêm a arquitetura das v1.22–v1.24, apenas com material, bordas e spacing harmonizados.

## Limites deste ciclo
- Nenhuma migration.
- Nenhuma alteração de schema, endpoint, banco, Score Engine, automações, finanças ou regras comerciais.
- Nenhuma nova feature de produto.
- A v1.25.0 encerra o roadmap de reconstrução mobile + polish iniciado na v1.21.0.
