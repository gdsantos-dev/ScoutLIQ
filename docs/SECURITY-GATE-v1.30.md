# Revisão de segurança — fatia operacional 1.30

Escopo: migração 019, opportunity_models.py, opportunity_workflow.py, pontos de integração em main.py, api.ts e nova ficha. Revisão de código e testes locais; não representa pentest, scan exaustivo do produto ou aprovação de deploy.

| Área | Verificação e resultado |
|---|---|
| Autenticação, autorização e sessões | Novas rotas dependem de current_user; mesmas sessões hash/expiração/conta ativa existentes. Nenhuma autenticação alternativa. |
| IDOR/BOLA e isolamento | Lead e filhos exigem user_id; evidência/rascunho também precisam pertencer ao lead da URL. Testes negativos entre usuários e entre leads. |
| Broken Access Control e privilege escalation | Todas as operações validam no servidor; UI não concede autorização. Leads fictícios/encerrados não aceitam preparação/revisão. Sem campos de role/plano/owner nas entradas. |
| Mass assignment | DTOs explícitos extra=forbid; testes rejeitam user_id e status fornecidos na criação de rascunho. Estado, autoria, timestamps e hash são definidos no backend. |
| SQL Injection | Consultas via SQLAlchemy com parâmetros. Nenhuma concatenação de SQL nas novas rotas. |
| NoSQL Injection | Não há banco NoSQL nem passagem de filtros/operadores arbitrários nesta fatia. |
| XSS e conteúdo externo | React renderiza texto escapado; sem HTML injetado. URL de evidência aceita somente HTTP(S), host presente e sem credenciais. Testes rejeitam javascript/file e URL com senha. Texto externo nunca executa código ou ações. |
| SSRF | A nova ficha não busca a URL informada; apenas referencia a fonte. Importação usa a pesquisa já existente, cujo fetch protegido foi preservado. Nenhum novo cliente HTTP. |
| CSRF/CORS | Mutações usam a proteção atual de token e Origin. Teste sem CSRF retorna 403. Nenhuma ampliação de CORS. |
| Rate limiting e brute force | Limites existentes mantidos: mutações por usuário, login por conta/IP. Evidências limitadas a 200/lead e drafts a 50/lead; seleção até 8 evidências, corpos e strings limitados. Store de rate limit continua em memória e exige uma réplica; não foi anunciado como distribuído. |
| Concorrência, idempotência e duplicação | Versionamento otimista em evidência/draft/lead. Chave única user_id+request_id impede duas preparações com a mesma chave; reuso com payload diferente retorna 409. Captura da mesma pesquisa é deduplicada por lead+timestamp+check. Não há envio externo a duplicar. |
| Aprovação | Hash vincula conteúdo, destinatário, canal, idioma, versões de evidências, versão do lead e referência/validade da autorização. Edição revoga aprovação. Dispatch revalida validade e mudanças, depois falha fechado por ausência de adapter. Testes cobrem edição, refutação e vencimento. |
| Preferências/respostas | Recusa pausa drafts e impede preparação/aprovação e registros de contato do mesmo lead. Resposta registrada no CRM pausa drafts de e-mail e WhatsApp. Bloqueio entre identidades duplicadas e sequências globais não foi implementado. |
| Cookies/tokens/HTTPS | Configuração existente HttpOnly/SameSite=Strict/Secure em produção preservada. Não homologado em domínio HTTPS nesta execução. |
| Secrets/variáveis de ambiente | Sem novos tokens de provedor; nenhuma chave no frontend. FULL/PATCH excluem .env, bancos, caches e runtime. .env.example contém a configuração de referência. |
| Logs e tratamento de erro | Nenhum conteúdo de mensagem/autorização é registrado em logs operacionais pelas rotas novas. Histórico privado autorizado contém eventos de revisão. Erros seguros existentes preservados. Frontend rejeita JSON inválido e trata timeout de mutação como resultado não confirmado. |
| Headers/CSP | Middleware existente preservado. CSP herdada inclui unsafe-eval; esta sessão não auditou a necessidade dessa permissão em toda a stack do mapa. Não afirmar CSP estrita sem essa ressalva. |
| Dependências | source-map-js atualizado de 1.2.1 para 1.2.2 após alerta GHSA-68fv-2mgg-jv7q. npm audit final e pip-audit do requirements.lock retornaram zero alertas conhecidos na data da sessão. |
| Retenção, exclusão e exposição | Novas tabelas possuem cascade para usuário/lead. Exportação privada inclui os novos dados e omite hash interno de aprovação. Backup SQLite continua integral. Retenção automática, criptografia de campos e trilha imutável não foram adicionadas. |
| Uploads, deserialização e command injection | Sem uploads, pickle, eval ou comandos de sistema originados de entradas nas rotas novas. JSON tipado; sem execução dinâmica. |
| Webhooks, pagamentos e cobrança | Não adicionados. Autenticidade/deduplicação de webhooks e outbox de comunicação serão obrigatórias antes da integração oficial. Finanças existentes não foram reescritas. |
| Endpoints administrativos | Sem novas rotas administrativas. Administração existente por chave de servidor e suas limitações permanecem fora da mudança. |
| IA e prompt injection | Nenhum modelo de linguagem executa decisões nesta fatia. Geração determinística usa somente evidências confirmadas selecionadas. Conteúdo externo é dado, nunca instrução. |

Não houve envio comercial, cobrança, publicação ou transmissão de contatos a provedores. O código de `/dispatch` responde 503 mesmo quando a aprovação é válida. OAuth e adapters reais **não estão implementados**, não bastando inserir credenciais para ativar envio.

Antes de produção: revisar os itens de deploy do SECURITY.md original, validar HTTPS/cookies/origem no domínio final, restaurar backup em ambiente controlado, resolver limitações de UX registradas e definir retenção/permissões operacionais. A nova fatia não autoriza disparos nem torna o produto inteiro homologado.
