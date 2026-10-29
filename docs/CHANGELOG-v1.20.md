# ScoutLIQ 1.20.0 — redesign

Base: `ScoutLIQ-v1.19.1-campaigns-typescript-hotfix-full.zip`. UX: handoff premium MD de 27/09/2026. Nenhuma alteração de backend, modelos, DTOs, permissões, cálculo de scores ou migrations.

## Arquitetura da experiência

- Workspace com ambientes Operar e Gerir clientes, cada um lembrando sua última área durante a sessão.
- Radar como entrada. Overview removido; ações pendentes aparecem no contexto da gestão e tendências ficam no Financeiro.
- Busca por comandos com navegação, empresas por nome/cidade/endereço/telefone, campanhas, cadastro e interpretação de pesquisa. Cmd/Ctrl+K e navegação por teclado.
- Context Panel novo, progressivo e sensível ao ambiente. Resumo, Análise, Pesquisa e Relacionamento preservam score/confiança/timing, fit, concorrência, diagnóstico, auditoria, enriquecimento, contatos e histórico. Clientes continuam derivados de Lead + Sale, sem tabela nova.
- Oportunidades e Monitores têm superfícies próprias. Campanhas continuam ligadas aos resultados comerciais reais; Automações ficam no menu do workspace e nos comandos.

## Operação e gestão

- Radar: canvas, toolbar, busca e filtros em painéis dedicados, resultados laterais no desktop e painel inferior expansível no celular.
- Clusters por proximidade na tela limitam a quantidade de marcadores; a lista completa continua acessível. Resultados são exibidos em blocos de 60. Seleção, território, bounds/polygon, centralização e controles explícitos de zoom preservados.
- Buscas salvas e frequência de monitoramento usam os contratos existentes. Pesquisa em Oportunidades respeita os IDs retornados; abrir a área sem pesquisa mostra a base completa aplicável.
- Negociações reorganizadas por etapas, próximas ações e valores. Mudança por seletor ou arrastar para etapa; fechamento segue o formulário de venda e a transação existente.
- Clientes abrem contexto comercial ou gestão de pagamentos. Sites preserva campos, alertas, margem, renovação, links e status. Financeiro mantém moedas separadas e acrescenta tendência no contexto financeiro.

## Design e engenharia

- Tokens acromáticos e crimson, sem paletas de status concorrentes. Preferências antigas de accent permanecem no banco, enquanto a identidade desta versão é crimson.
- Tipografia legível, superfícies contínuas, menos microtexto, alvos de toque, controles próprios e estados vazios/erro/offline.
- Seletor acessível com teclado e opções dentro de diálogos; calendário próprio com setas, foco e limites de data. Nomes acessíveis nos filtros e formulários.
- Fonte Inter local reduzida ao conjunto latino; Context Panel, mapa, gráfico e páginas carregados sob demanda. MapLibre mantém um worker e zoom por controle; nenhuma biblioteca visual nova.
- `@types/node` acrescentado somente ao desenvolvimento para checar testes e fixtures com TypeScript estrito.
- Formatadores funcionam também fora do DOM. Testes antigos que dependiam da sidebar/Overview/select nativo foram substituídos por cenários que exercitam o fluxo atual.
- Pacote completo sem dados de runtime e patch com hashes da base, pré-validação integral, backup e restauração em falha de cópia.

## Arquivos principais

Novos: `WorkspaceShell.tsx`, `CommandBar.tsx`, `ContextPanel.tsx`, `navigation.ts`, `search.ts`, `workspace.css`, `workspace.i18n.ts`, `fonts.css`, testes e documentação da versão. Removidos: `Overview.tsx`, `LeadDrawer.tsx` e a suíte antiga de navegador. Recompostos: App, Radar, Pipeline, Clients, Finance, Settings, Campaigns, Automations, primitives e estilos compartilhados. A relação exata com hashes fica em `CHANGED-FILES.json` junto aos pacotes e no `PATCH-MANIFEST.json` do patch.
