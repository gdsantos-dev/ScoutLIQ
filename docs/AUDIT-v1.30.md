# ScoutLIQ — auditoria e primeira fatia operacional

Data: 09/10/2026. Base técnica: ZIP v1.29.0 fornecido pelo usuário. O pedido colado é a autoridade de escopo; documentos históricos do ZIP foram tratados como registros a conferir, não como novas instruções.

## Base e arquitetura confirmadas

- SHA-256 do ZIP: `f38b0f3576ef0748e3f5998e499b2fe8c481cdeec0b87a028b85680a9026f182`.
- `frontend/package.json`, lockfile, Sobre e exportador Bridge identificam 1.29.0. Os 196 hashes do manifesto correspondem aos arquivos recebidos. O ZIP tem 197 arquivos, incluindo o próprio manifesto. Não contém histórico Git que permita atribuir um commit de origem.
- A pasta histórica v1.20 não foi substituída. Baseline extraída em `work/v1.29.0-audit/ScoutLIQ`; implementação em `work/v1.30.0/ScoutLIQ`.
- React 19, TypeScript 5.9, Vite 7, MapLibre, Recharts e Motion. SPA com rotas por hash, dois ambientes e componentes de contexto compartilhados. Configurações efetivas estão no package-lock.
- FastAPI 0.135.1, SQLAlchemy 2.0.48, Alembic 1.18.4, Argon2 e SQLite. Dependências Python do ambiente conferidas contra requirements.lock, sem divergências.
- Revisão Alembic original: 018. Dois arquivos começam por `007`, mas os metadados de revisão formam uma cadeia executável: os 107 testes originais passaram com upgrade até head. Nomes de arquivo não foram tratados como prova de migração duplicada.
- `backend/main.py` concentra rotas e orquestração; `research.py`, `scoring.py`, `providers.py`, `enrichment.py` e `automation.py` já separam capacidades reutilizáveis. Rate limiting e cache são locais ao processo. A política existente exige SQLite com uma réplica/worker.

## Inventário verificável da v1.29

C = código inspecionado; T = testes locais executados; UI = observação automatizada da interface. Funcional significa que o mecanismo existe e tem evidência local, não homologação em produção.

| Capacidade | Classificação | Evidência e reutilização |
|---|---|---|
| Login, sessões, confirmação/recuperação | Funcional; entrega de e-mail depende de provedor | C: security.py, email_service.py, main.py. T: test_auth_accounts, test_api. UI: login local. Argon2, token de sessão hash, CSRF e expiração preservados. |
| Permissões/isolamento | Funcional no escopo testado | C: current_user e filtros user_id/owned. T: isolamento, admin, autenticação. Modelo por usuário, sem inventar um novo tenant compartilhado. |
| Descoberta de empresas | Parcial na operação externa | C: providers.py, Geoapify e OSM/Nominatim/Overpass; importação de link Google Maps. T: test_radar e test_radar_query usam contratos controlados. Credenciais, cobertura e resultados ao vivo não homologados. |
| Deduplicação | Funcional com limites | C: source_id e _lead_identity; nome/localização e dados de identidade. Não é resolução universal de entidades. Homônimos continuam exigindo revisão de cidade/endereço/telefone. |
| Enriquecimento e pesquisa | Funcional local; dependente de fontes | C: research.py/enrichment.py; fontes, confiança, checks, limites HTTP/SSRF. T: test_research. Reutilizar todo o motor. HTML não comprova acessibilidade completa nem UX mobile. |
| Radar/mapa/filtros | Funcional com dependência externa | C e UI: Radar, mapas, lista, filtros e pesquisas salvas. Tiles/rede/WebGL são externos. Lista permanece alternativa. |
| Monitoramentos e lotes | Parcial | C: estado persistido em RadarSavedSearch e ResearchBatch/Item. Radar.tsx aciona monitor e /step via efeitos/timers do navegador. Fechar o navegador interrompe a execução ativa; persistência não equivale a worker. |
| Opportunity Score | Funcional | C: scoring.py; score versionado, confiança, dimensões, nicho, diagnósticos, fit por serviço, timing e sinais. T: test_scoring. Preservado byte a byte. Não foi criado outro score. |
| Ficha de oportunidade | Parcial | C/UI: ContextPanel já reúne resumo, análise, pesquisa e histórico. Evidências de pesquisa são snapshots JSON substituíveis, sem revisão individual durável. Evoluída nesta versão. |
| Pipeline e clientes | Funcional | C: Lead, Sale, Payment, LeadActivity; páginas Pipeline/Clients. T: test_api/test_campaigns_insights. Cliente continua derivado do lead/venda, sem nova entidade concorrente. |
| Sites, entrega e financeiro | Funcional local | C/T: Site, alertas, custos, moeda, margem e idempotência financeira. Sem alterações nos cálculos ou entidades existentes. |
| Propostas e contratos | Parcial / ausente | Proposta pode ser registrada como atividade. Não há editor/assinatura de contratos ou mecanismo completo de geração de proposta. Não foi criado nesta fatia. |
| Outreach manual | Legada em transição; funcional como assistência | C: outreach.ts, OutreachComposer, localStorage, mailto/wa.me, registro manual. Não há confirmação de envio pelo provedor; templates persistem só no navegador. Mantido com identificação explícita de registro manual. |
| Campanhas e aprendizado | Funcional determinístico | C/T: Campaign/Lead, atribuição, snapshots e métricas de resultados. Não é aprendizado automático. Reutilizar para calibração futura. |
| Regras de automação | Parcial | C/T: AutomationRule/Run e gatilhos de eventos síncronos, condições, limites de execução por lead, histórico. Sem fila dedicada, backoff, leases, DLQ, orçamento por provedor ou worker de recuperação. |
| Notificações | Parcial | Contagens e sinais na interface; não foi localizado um serviço completo de notificações persistentes de jobs/approvals. |
| Gmail/WhatsApp oficiais | Ausente | Sem OAuth comercial, adapters de envio, webhooks de resposta, bounces ou unsubscribe global entre identidades. O e-mail transacional de conta não é motor de prospecção. |
| Integração ORLIQ/DashLIQ | Parcial, contrato portátil | C/T: ecosystemBridge.ts exporta orliq.bridge v1 com IDs e centavos. Sem transporte automático ou importador DashLIQ validado nesta sessão. |
| Desktop/mobile | Parcial | Duas superfícies existem. A suíte histórica expõe problemas fora da ficha; consultar VALIDATION. Não houve redesign integral nesta execução. |

Nenhuma duplicação de CRM ou Opportunity Score foi identificada como necessária. A sobreposição principal está nas camadas históricas de CSS e em diversas representações de sinais, que devem convergir pelo mesmo Lead, não por novas cópias de oportunidades.

## Problemas confirmados e prioridade

1. **Build original quebrado:** TS6133 em historyIntelligence.test.ts, argumento `index` sem uso. Corrigido.
2. **Automação depende do navegador:** não oferece operação contínua. Próxima prioridade estrutural: mover execução dos ResearchBatchItem existentes para worker com claim/lease e retentativas; não criar fila paralela para a mesma investigação.
3. **Outreach sem aprovação persistente:** registro manual não prova envio. Nova camada servidor implementada nesta fatia, sem fingir conexão com provedores.
4. **Fatos sem revisão individual:** snapshots não registram refutação/versionamento por afirmação. Nova camada de evidência referencia pesquisa existente e grava revisões em LeadActivity.
5. **Resposta JSON inválida podia parecer sucesso:** api.ts antes retornava um objeto de erro tipado como resultado. Agora rejeita e indica resultado não confirmado para mutações.
6. **Scripts de release obsoletos:** build/verify ainda pressupunham 1.19.1 e layout do ZIP antigo. Corrigidos e validados com base exata 1.29.0.
7. **Overflow de 4 px em Negociações/320 px:** largura expandida/margem negativa não correspondia ao padding real. Regra original corrigida.
8. **Dependência com alerta alto:** source-map-js 1.2.1, GHSA-68fv-2mgg-jv7q. Atualização transitiva para 1.2.2; auditorias posteriores sem alertas conhecidos. Não é declaração de ausência de vulnerabilidades no produto.

## Arquitetura consolidada

Lead continua sendo a identidade da oportunidade. LeadResearch armazena a investigação atual; OpportunityEvidence guarda afirmações com fonte e revisão explícita; OutreachDraft guarda conteúdo e aprovação. LeadActivity é a única timeline. Sale/Payment/Site continuam sendo a camada de clientes, entrega e financeiro. Nenhum serviço externo novo foi adicionado.

A necessidade das duas tabelas novas foi conferida no inventário: Research não possui a revisão individual de afirmações, e templates locais não armazenam rascunhos por oportunidade. As novas tabelas não substituem a pesquisa nem o CRM.

A avaliação usa o score existente. Cobertura da ficha é uma contagem de evidências válidas, não outra nota de potencial. Observações HTML importadas começam como prováveis; sinal ausente é descrito como pendente de verificação, nunca como ausência universal de uma capacidade.

## Ordem das próximas sessões

1. Workers para os lotes e monitores existentes: claims atômicos, lease, retry/backoff, recuperação, cancelamento, orçamento e rate limits por provedor. Definir migração de autoridade navegador→servidor antes de ativar ambos.
2. Motor único de comunicação: persistir templates existentes, OAuth oficial, elegibilidade legal por mercado, consentimento, destinatário canônico e bloqueio global entre registros duplicados. Integrar a aprovação atual; não criar outra fila de mensagens.
3. Outbox transacional e adapters Gmail/WhatsApp, idempotência por entrega, estado incerto após timeout, webhooks autenticados, deduplicação, respostas e suspensão de sequências. Homologar em contas controladas antes de qualquer envio comercial.
4. Ampliar ficha/ações para propostas e resultados, calibrar prioridades com métricas existentes e separar claramente regras/heurísticas/LLM opcional com orçamento.
5. Refinar superfícies Operacional/Gestão e consolidar CSS por componente, sem reescrita do backend. Referências consultadas: [Refero](https://refero.design/) e [Attio](https://attio.com/). A página pública da ORLIQ não foi fornecida nem homologada como referência visual nesta sessão.

## Limites desta entrega

O percurso entregue vai de pesquisa existente ou observação com fonte até evidência revisada, classificação existente, ficha, rascunho persistido, aprovação e histórico. **Execução e resposta pelo provedor permanecem não implementadas**: `/dispatch` revalida a aprovação e termina com HTTP 503, sem efeitos externos. Não se trata de integração pronta aguardando somente credenciais.

Preferências e pausa de rascunhos abrangem os dois canais da mesma oportunidade. Bloqueio global entre empresas/contatos duplicados e sequências futuras ainda exigem modelo de destinatário canônico. A trilha é auditável no aplicativo, não imutável contra um administrador do banco. As mensagens EN/ES mantêm o texto original das evidências: tradução contextual e localização completa da nova ficha são pendências explícitas.
