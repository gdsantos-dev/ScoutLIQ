# ScoutLIQ 1.24.0 — Módulos restantes no mobile

## Objetivo
Quarto ciclo pós-redesign da v1.20.0. A v1.23.0 permanece como baseline funcional e este release fecha a recomposição mobile das superfícies que ainda herdavam leitura e composição de desktop.

## Oportunidades
- A superfície em lista passa a usar o espaço real do celular, sem padding duplicado do ledger desktop.
- Busca, filtros e lista inteligente ficam numa faixa touch compacta e rolável quando necessário.
- Cada oportunidade ganha leitura vertical mais clara: score, identidade, sinal principal e contexto em chips compactos.
- Ações e filtros continuam ligados ao mesmo Radar, Score Engine e handlers existentes.

## Monitores
- O resumo de monitoramentos vira uma faixa de indicadores compacta, sem três cards genéricos.
- Buscas monitoradas passam a priorizar nome, escopo e frequência em leitura vertical.
- Controles de frequência, ativação e exclusão ficam dimensionados para touch.
- Watchlist e mudanças continuam usando os mesmos dados e endpoints da v1.23.0.

## Campanhas
- A seleção de campanha vira uma faixa horizontal com snap, adequada ao polegar.
- O detalhe passa a ser uma sequência única: status, métricas, receita atribuída e empresas.
- Métricas são recompostas para 2 colunas e o quinto indicador ocupa a largura inteira.
- Criação, atribuição, membros e insights de ganhos/perdas mantêm as mesmas regras.

## Automações
- Criar ou editar uma automação abre um workspace mobile dedicado entre o masthead e a navegação inferior.
- Condições e ações deixam de depender de grids comprimidos e passam a blocos verticais touch-first.
- Condições de parada ganham alvos maiores e leitura mais direta.
- A barra de salvar/cancelar permanece alcançável na base do editor durante a rolagem.
- Nenhuma regra do motor de automações foi alterada.

## Configurações e About
- Configurações passa a ser uma sequência única de seções no celular, eliminando a malha desktop.
- Ações principais ocupam a largura útil e opções de movimento ficam em linhas próprias.
- O bloco de marca vira um rodapé discreto com a versão atual.
- About recebe composição editorial compacta para produto, release, infraestrutura, workspace e princípios.

## Formulários e estados vazios
- Modais gerais passam a funcionar como bottom sheets no celular, com cabeçalho e ações persistentes.
- Form grids deixam de manter colunas de desktop em viewport estreito.
- Estados vazios deixam de ocupar blocos gigantes e passam a informar e liberar ação sem desperdiçar tela.

## Limites deste ciclo
- Desktop preservado estruturalmente.
- Nenhuma migration.
- Nenhuma alteração de schema, endpoint, banco, Score Engine, regras comerciais ou regras financeiras.
- A próxima etapa permanece a v1.25.0: Visual Polish geral de desktop + mobile.
