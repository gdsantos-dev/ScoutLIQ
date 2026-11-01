# Arquitetura — v1.38.8-dev

## Continuidade canônica

`ProspectingPlan → PlanDecision → RoutineRun → SmartSearch → ResearchBatch → ResearchBatchItem → WorkAttempt/ProviderOperation → Lead/Score/evidências → CommercialReview → CommercialOperation → OutreachDraft`.

A descoberta continua no worker existente. `create_search` captura as preferências de investigação somente quando o opt-in de pesquisas está ativo. No caminho SmartSearch, `_persist_discovery` não gera lotes avulsos. Após a incorporação, `investigation.enqueue` admite um lote progressivo limitado e associa `SmartSearch.batch_id` antes do commit. As demais origens conservam seu comportamento. Sem opt-in, o caminho legado existente permanece.

São admitidas apenas empresas novas não descartadas, respeitando cooldown, lotes pendentes e limites. O teto é o menor valor entre limite da pesquisa, configuração capturada e configuração atual de execução. Desativar o opt-in impede novas admissões. Há no máximo um lote por SmartSearch; excedentes exigem decisão posterior. Nenhuma pesquisa histórica é reprocessada automaticamente.

Ao alcançar a meta, `run_block` permite somente a investigação já admitida. Dia, janela, consentimento, estado, fonte e limites de operações ainda podem impedir a execução. Depois do lote, a pesquisa faz reclassificação local e termina sem pedir outra página ao provedor. Pausar ou revogar continua usando cancelamento e fencing existentes.

## Projeção diária na fila comercial

`GET /api/commercial-review/queue?view=daily` reutiliza autenticação, rate limit, lock por usuário e índices canônicos de revisão/acompanhamento. Não cria relatório ou motor decisório concorrente. O máximo de 250 atualizações locais por chamada permanece explícito em `index_pending`.

Filtros diários: atenção (`response`, `ready`, `stale`, `pending`, `blocked`) e população (`all`, `today`, `plan`), além dos filtros existentes. `lead_ids` aceita até 50 UUIDs para revalidar a seleção; todos os IDs continuam limitados ao usuário autenticado. Não há autorização por conhecimento de ID.

A ordenação usa precedência operacional, vencimento, Score canônico decrescente e ID estável. Respostas exigindo ação vêm primeiro; oportunidades investigadas prontas e ações humanas vencidas são urgentes; seguem revisões desatualizadas, investigação/dados pendentes e bloqueios. Não se somam pontos nem se alteram pesos. Cada linha fornece o motivo derivado do acompanhamento e da qualificação existentes.

Estados encerrados, pausados, concluídos e aguardando retorno não entram como pendência diária. Escolhas adiadas ou não prioritárias são preservadas; contexto alterado, resposta ou bloqueio pode tornar a revisão necessária novamente. Ausência de dados continua explícita. Ver todas as empresas ou decisões continua disponível nas visões canônicas.

O resumo usa agregações SQL por usuário e dia local, sem chamar provedores ou carregar o relatório completo de Inteligência. Meta e novas empresas conservam a definição de 1.38.7: todas as origens reais, sem duplicar reencontros. `plan_incorporated` separa o crédito do plano; `other_incorporated` representa as demais origens. `investigated` exige item concluído; `qualified` usa a classificação prioritária existente; `ready` exige também revisão pendente e ausência de bloqueio/estado final. Esses números não medem conversão comercial.

Datas usam o fuso da conta. Mudanças de fuso, exclusões e descartes anteriores à observação de 033 limitam comparação histórica. A API informa cobertura parcial do índice e limites de listagem: 20 pesquisas, cinco decisões e cinco operações recentes. Dados de hoje são estados atuais das empresas incorporadas hoje; a fila pode incluir pendências anteriores.

## Interface e operações humanas

Radar → Fila comercial → Operação do dia. Resumo compacto e mesma lista, detalhe, prévia e confirmação. Atalhos levam às rotinas, histórico de pesquisa, investigação e operações existentes. O indicador de qualificadas filtra aquelas que ainda exigem atenção; outras decisões continuam na Triagem. Nenhum novo painel ou CRM.

A seleção permanece ao trocar visões e após confirmação. A resposta da operação recupera as versões atuais dos IDs selecionados para a próxima prévia; os efeitos já executados continuam consultáveis mesmo se a atualização posterior falhar. Falhas, bloqueios e conflitos são individuais. O limite de 50, idempotência, prévia e confirmação não mudam.

A atualização da visão ocorre a cada 15 segundos somente com página visível e sem operação aberta ou ação em andamento. Não dispara pesquisa, investigação, rascunho ou envio. O detalhe pode selecionar a empresa atual para a operação canônica de investigação.

## Persistência e segurança

Revisão **033**, sem novas tabelas ou migração. Estado adicional ocupa o JSON existente de SmartSearch. Identidade, LeadActivity, Score 3.0, CommercialFit, evidências, orçamento, RecipientPolicy e OutreachDraft permanecem canônicos.

ORM parametrizado, validação de enums/UUIDs/limites, filtros de proprietário e React com escape de texto. Nenhum novo segredo, upload, webhook, comando de sistema, integração externa ou endpoint administrativo. A leitura da fila pode atualizar apenas os índices derivados, como já ocorria. Todas as mutações comerciais continuam autenticadas, protegidas por CSRF, validadas por versão e confirmação explícita.
