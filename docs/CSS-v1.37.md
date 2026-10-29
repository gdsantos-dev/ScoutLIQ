# Organização e consistência do CSS — v1.37

styles.css e workspace.css agora são índices ordenados de módulos por superfície em frontend/src/surfaces/. Foram extraídos 31 módulos de base e 13 de workspace (44 ao todo). A sequência das regras foi preservada byte a byte na extração; a referência relativa a tokens.css foi ajustada à nova pasta. A extração não promete redução de bytes no bundle e não altera a especificidade para esconder conflitos.

Busca e revisão têm estilos próprios: unified-search.css e commercial-review.css. Radar mantém radar-workspace.css. WorkspaceShell e WorkflowSteps continuam encapsulados. Novos controles usam design tokens, respeitam reduced-motion e evitam novos blocos de overrides genéricos.

Correções funcionais incluem checkbox com 18 px em vez da altura dos campos, alvo de toque mínimo, quebra de linhas, limites de altura do diálogo, scroll interno e backdrop isolado. O lifecycle compartilhado controla múltiplos diálogos, foco, Escape e restauração do documento. Nenhum listener global bloqueia indiscriminadamente wheel/touch.

Evidência de equivalência da extração: evidence-v137/css-surface-equivalence.json. A validação de layout cobre Radar, ficha, gestão, configurações, integrações, mapas e formulários nos E2E. A base histórica continua contendo regras globais de controles compartilhados; não se afirma que todo o produto foi convertido em CSS Modules.
