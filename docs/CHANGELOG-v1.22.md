# ScoutLIQ 1.22.0 — Radar Mobile

## Objetivo
Segundo ciclo pós-redesign da v1.20.0. A v1.21.0 permanece como baseline funcional e este release recompõe o Radar para celular sem alterar backend, banco, Score Engine, automações ou contratos de API.

## Radar como superfície mobile
- O mapa passa a ocupar a área útil inteira entre o masthead e a navegação inferior.
- Busca, filtros e alternância de visualização permanecem acessíveis sobre o mapa com alvos adequados para touch.
- Ações de área visível e território usam controles compactos próprios para celular, sem transportar a barra desktop para a tela estreita.
- A visualização em lista continua disponível como alternativa, mas o mapa é a entrada principal do Radar.

## Resultados em bottom sheet
- Resultados usam três níveis: `peek`, `mid` e `full`.
- O handle aceita toque/clique e gesto vertical por pointer para avançar ou recolher o painel.
- `peek` mantém o mapa dominante e mostra contexto mínimo dos primeiros resultados.
- `mid` libera filtro local e mais contexto de cada empresa.
- `full` transforma o painel em workspace de resultados e exibe as ações complementares.
- A busca concluída abre os resultados em `mid`, evitando esconder o mapa e evitando também uma lista microscópica.

## Busca, filtros e territórios
- Nova pesquisa, filtros e buscas salvas viram sheets ancoradas na parte inferior em telas mobile.
- Formulários passam para uma coluna e mantêm ações em área sticky, evitando botão perdido depois de uma rolagem longa.
- Campos, selects e ações relevantes usam altura mínima adequada para toque.
- Controles de `Nesta área` e `Território` permanecem posicionados acima do nível atual do sheet.

## Contexto progressivo da empresa
- Ao abrir uma empresa no celular, o Context Panel entra como sheet compacto com o resumo essencial.
- O usuário pode expandir a superfície pelo handle.
- Ao abrir Análise, Pesquisa ou Relacionamento, o painel expande automaticamente.
- Desktop mantém o painel lateral já existente.

## Limites deste ciclo
- Gestão Mobile continua reservada para a v1.23.0.
- Campanhas, Monitores, Oportunidades, Automações e demais telas ficam para ciclos posteriores conforme o roadmap.
- Nenhuma migration.
- Nenhuma alteração de schema, endpoint ou regra de negócio.
