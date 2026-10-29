# Arquitetura V1

## Execução

O mesmo serviço entrega arquivos estáticos compilados e `/api`. Nenhum Node.js em produção. API síncrona com SQLAlchemy roda no threadpool do FastAPI; um worker Uvicorn mantém custo baixo e limitações de rate limit claras. SQLite usa WAL, foreign keys e timeout de lock. Migrações executam no início, quando o volume Railway já está montado.

## Domínio e consistência

`User` configura a operação. `Session` armazena hash do token, CSRF e expiração. Todos os dados comerciais possuem `user_id` e consultas autorizadas no servidor. A primeira versão oferece uma conta inicial privada, sem convite/registro público.

`Lead` mantém evidências do estabelecimento e etapa comercial. `in_pipeline` distingue descobertas ainda não trabalhadas. Alterações usam coluna de versão: uma edição com versão antiga recebe 409. Não há refresh periódico; a interface carrega dados na entrada, após mutações e por atualização explícita.

`Sale` transforma o lead em cliente e guarda serviço, valor, datas, status de projeto e manutenção mensal. Uma venda por lead nesta V1. `Payment` registra caixa recebido. `Expense` registra custo. Todos os valores são centavos inteiros em BRL. Venda/fechamento são atômicos. Pagamentos bloqueiam o saldo antes de validar e inserir; não excedem o total. Chave de reenvio evita duplicação no retry. Vendas fechadas não voltam a etapas abertas, preservando a consistência do financeiro.

Vendas do dia usam `sold_on`, que é uma data comercial, no fuso configurado. O gráfico Hoje apresenta um ponto diário porque a V1 não registra hora comercial da venda. Os demais períodos possuem buckets diários. Resultado de caixa = recebimentos − custos; recorrência contratada não é caixa nem gera cobrança automática. V1 não implementa estorno/cancelamento financeiro; não editar o banco informalmente para corrigir operações reais. Planejar estornos rastreáveis antes de ampliar o uso.

## Fontes de estabelecimentos

`EstablishmentProvider.search(DiscoveryQuery) -> DiscoveryBatch` é o contrato em `backend/providers.py`. Em produção, `auto` seleciona Geoapify quando a chave está configurada; a geocodificação, busca de lugares e enriquecimento de detalhes acontecem somente no backend. OpenStreetMap/Overpass continua disponível por configuração explícita para desenvolvimento. URLs, timeouts, limites e provider são configuráveis por ambiente; nenhuma API key vai ao bundle. O browser fala apenas com `/api/radar/search`, então Railway e localhost mantêm a mesma origem de API.

Resultados externos são normalizados para `Lead`, recebem `source` + `source_id` e são persistidos antes de aparecerem no mapa. A deduplicação prefere o ID externo e usa como fallback identidade composta por nome, cidade, endereço, telefone e coordenadas; nome isolado nunca identifica uma empresa. Dados que a fonte não oferece, como avaliações Google ou atividade recente do Instagram, permanecem desconhecidos. O mapa recebe somente entidades normalizadas e continua independente do provider.

## Score v1.2

Pesos em `backend/scoring.py`: sem site confirmado +35 OU site com problemas confirmados +25; em descoberta por fonte aberta (OpenStreetMap/Geoapify), ausência de site informado vale somente +15 e não é tratada como confirmação; 100+ avaliações +18 OU 20+ +9; nota 4,5+ +12 OU 4+ +6; Instagram ativo confirmado +10 ou Instagram apenas listado +5; telefone +10; WhatsApp informado +15. Máximo 100. Evidência ausente = 0. O valor é prioridade determinística, não probabilidade. A V1 não inspeciona a qualidade técnica de sites nem faz scraping de redes sociais.

## Frontend

React e TypeScript, páginas carregadas sob demanda, funções de API centralizadas. Estados de autenticação, carregamento, erro e dados vazios são explícitos. As mutações mantêm feedback e bloqueio enquanto salvam. Pipeline possui atualização otimista com recuperação após falha. Forms validam UX e backend valida autoridade. Dialog nativo cuida de foco/trap nos formulários; drawer tem foco, Escape e restauração.

O componente de mapa consulta `/api/radar/map-config`. Com `RADAR_MAPTILER_API_KEY`, o MapLibre carrega o Style JSON do MapTiler (`dataviz-v4-dark` por padrão, ou `RADAR_MAPTILER_STYLE_ID`), mantendo controles próprios, markers customizados e fit automático. Se a configuração estiver ausente ou o estilo MapTiler falhar na inicialização, o componente cai para MapLibre + tiles OpenStreetMap sem interromper a lista. O mapa permanece independente do provider de descoberta e não usa a chave server-side do Geoapify. O frontend carrega `/api/radar/locations` uma vez por montagem do Radar e filtra o catálogo de municípios localmente enquanto o usuário digita; selecionar uma sugestão envia cidade + UF de forma estruturada. A geocodificação da busca final continua no backend.

## Evolução

PostgreSQL: adicionar driver psycopg, configurar URL, validar migrações e testes de concorrência no dialeto. Remover restrição de réplica apenas após rate limit compartilhado, estratégia de migração concorrente e validação operacional.

DashLIQ: exportação JSON v1 inclui UUIDs estáveis para venda, pagamento e custo. O consumidor futuro deve implementar ledger de IDs já importados e transação idempotente. Esta versão apenas exporta; não afirma compatibilidade com um importador inexistente.


## Gestão de sites

Migração 002 adiciona `sites`, com proprietário e venda vinculada. Todo CRUD verifica usuário tanto no site quanto no cliente/venda selecionado. Edições usam controle otimista de versão. A exclusão do registro não remove a venda nem faz ações na hospedagem externa. Remover exemplos também remove os sites ligados às vendas fictícias.

A receita, custo e margem mensal de Sites são projeções contratuais dos sites ativos, sem lançamentos automáticos no caixa. Custo anual do domínio fica separado da margem mensal para não distribuir implicitamente valores. Recebimentos e despesas efetivos continuam explícitos no Financeiro. Exportação JSON inclui sites com IDs estáveis. Alertas de até 30 dias usam o fuso da operação; SSL/disponibilidade são estados informados, sem probes ou polling. Links externos são validados HTTP(S) e nunca buscados pelo servidor.


### Radar: precisão de localização e relevância
Quando o usuário escolhe um município do catálogo IBGE, o frontend envia município, UF e estado de forma estruturada. O Geoapify é geocodificado como cidade e o `place_id` retornado é usado junto do raio solicitado, evitando que uma busca municipal vaze para outra cidade/estado. O backend ainda revalida país, UF e distância por coordenadas antes de aceitar cada estabelecimento.

A descoberta busca um conjunto maior de candidatos e só então prioriza sinais úteis para prospecção (site não informado, telefone/WhatsApp/Instagram e endereço), diversifica categorias em buscas sem nicho e remove uma lista conservadora de grandes redes nacionais/globais que normalmente não são prospects reais para venda de sites. Isso é filtragem determinística, não IA.

### Score Engine 2.3: reanálise e contexto competitivo

O score continua determinístico. `competitive_context_json` guarda uma evidência derivada do conjunto de leads próximos do mesmo nicho; amostras insuficientes são neutras. `POST /api/leads/{id}/reanalysis` seleciona pesquisa web e/ou auditoria profunda conforme cobertura e frescor das evidências e depois recalcula o contexto local. Nenhum desses fluxos interpreta ausência de dados como prova de ausência.

### Score Engine 2.4: estrutura comercial aparente e timing

A etapa final da Score Engine 2.0 adiciona duas leituras independentes do índice principal. `commercial_structure` mede apenas estrutura observável da operação, com componentes de tração pública, estrutura operacional, maturidade digital e acesso comercial. O valor não estima faturamento, patrimônio ou capacidade financeira.

`timing` mede se há motivo observável para priorizar a abordagem agora. O backend persiste em `commercial_signal_json` um snapshot compacto de avaliações, situação do site e canais encontrados, além de eventos recentes. Reobservações do Radar podem registrar crescimento relevante de avaliações, novos contatos e aumento de unidades com o mesmo nome/categoria/país. Pesquisa web e auditoria profunda podem registrar mudança de presença web. Eventos expiram para o cálculo de timing e sinais negativos, como um site recém-confirmado ou melhorado, podem reduzir o valor.

A estrutura e o timing não alteram o significado do score principal nem do fit por serviço. Eles aparecem como leituras auxiliares e explicáveis.


### Research & Automation 2.0 · parcela 1

O Radar separa a consulta ao provedor (`RadarSearchInput`) dos critérios comerciais persistidos (`RadarSavedQuery`). A interpretação de linguagem natural produz um plano estruturado e auditável; filtros por problema consomem apenas diagnósticos já verificados pela Score Engine. Buscas salvas mantêm snapshots filtrados e agenda de monitoramento (`next_monitor_at`). A execução automática inicial é oportunística no uso do Radar, com limite por sessão, deixando a agenda persistida pronta para um worker dedicado posterior.

## Research & Automation 2.0 · automation engine

A partir da v1.18.0, automações são regras persistidas e independentes dos módulos de UI. Eventos de domínio (entrada no Pipeline, mudança de etapa, Watchlist, score e enriquecimento) alimentam o mesmo motor. O motor avalia condições, verifica parada e só então executa ações. Cada execução ou bloqueio é persistido em `automation_runs`.

O enriquecimento comercial mantém proveniência compacta no próprio lead. O fluxo é incremental: dados existentes são preservados, fontes mais caras só são consultadas quando há lacunas e cada campo aceito registra origem, confiança e horário de verificação.

## Campanhas e aprendizado de desfecho (v1.19.0)

Campanhas são entidades separadas dos leads e usam `campaign_leads` como associação muitos-para-muitos. Receita só entra na atribuição de uma campanha quando `sales.campaign_id` aponta explicitamente para ela. Isso evita dupla contagem quando a mesma empresa participa de mais de uma campanha.

Ganhos e perdas registram `outcome_snapshot_json` no lead no momento do desfecho. Os insights usam esse snapshot quando disponível e recorrem ao estado atual apenas para registros históricos anteriores à feature. Os insights são descritivos, exigem amostra mínima e nunca reescrevem pesos da Score Engine automaticamente.
