# Revisão de segurança — v1.35

Revisão explícita das mudanças e testes locais em 18/10/2026. Não é pentest, auditoria externa, autorização jurídica ou aprovação de deploy. Serviços reais/HTTPS/infraestrutura externa não foram homologados.

| Área | Controle / evidência / limite |
|---|---|
| Secrets e ambiente | Segredos somente backend/env; exemplos vazios. Tokens cifrados com Fernet e vínculo usuário+conta. Exports/API de contas excluem credenciais. Pacotes excluem ambiente, banco, cache e logs. |
| Autenticação e sessão | current_user e sessão existente, expiração, usuário ativo e CSRF nos POST/PUT. OAuth state vinculado à sessão iniciadora, expiração e consumo atômico; callback validado antes de rede. |
| Autorização / IDOR / BOLA / Broken Access Control | Consultas por usuário em casos, importações, avaliações, propostas, histórico, contas, políticas e outbox. Associação de filho ao Lead. Worker confere usuário ativo e vínculos novamente. Testes cruzam IDs de outro usuário. |
| Mass Assignment / privilege escalation | StrictModel extra=forbid; DTOs por ação. user_id, actor, versões de critérios, estado da fila e tokens não são campos livres. Nenhuma rota nova permite alterar role/permissões. |
| SQL Injection | SQLAlchemy parametrizado. Migrações SQL estáticas. IDs não compõem SQL de operação. Testes/scripts de integridade usam apenas nomes de tabelas locais conhecidos. |
| NoSQL Injection | Não há NoSQL nem operadores recebidos do cliente repassados a banco. JSON importado é validado e não executado. |
| XSS / mensagens externas | React escapa texto; sem dangerouslySetInnerHTML nas novas funções. HTML de email convertido em texto, sem anexos/scripts/styles/iframe/URLs ativas; limite 4.000 caracteres. Mensagem não vira comando/prompt de execução. |
| CSRF / CORS | CSRF da sessão existente e restrição de Origin nos writes. OAuth GET usa state de uso único vinculado à sessão. Nenhum wildcard CORS introduzido. |
| Rate limiting / brute force | Proteções de login preservadas; operações novas com limites por usuário (OAuth, verificação, autorização, reconciliação, importação/calibração). Limites persistentes de dados, tarefas, HTTP e tentativas de envio. Não desabilitados para QA. |
| Validação / uploads | JSON até 64KiB no HTTP e 50 casos por importação. Sem upload de arquivo ao filesystem; navegador lê JSON como texto. Schemas rejeitam rótulo IA apresentado como humano, campos extras e entradas incompatíveis. |
| SSRF / redirects | Gmail usa endpoints HTTPS fixos, IDs de provedor restritos, transporte não segue redirects. Redirect OAuth deve ser exatamente o configurado na origem; não vem do browser. Fontes de evidências não são buscadas pela importação. Pesquisa web mantém proteções herdadas. |
| Command injection / desserialização | Não há shell, eval, pickle ou execução de conteúdo de usuário nas novas rotas. Scripts QA invocam argumentos fixos; ZIP/PATCH verifica caminhos e hashes antes de escrita. |
| Logs / erros | Erros de provedor resumidos sem payload/tokens. Filtro de access log remove query OAuth; no-referrer/no-store. Proxy externo precisa suprimir query e headers sensíveis por configuração própria. Eventos guardam estados e IDs, sem credenciais. |
| Headers / HTTPS / cookies | Headers de segurança e cookies herdados; callback sem cache/referrer. Produção exige HTTPS. CSP existente mantém permissões anteriores necessárias ao frontend/mapa; não foi ampliada para Gmail. Validação TLS/cookies reais do host permanece pendente. |
| Webhooks | Nenhum webhook novo exposto. WhatsApp só contrato, sem receptor que aceite eventos sem assinatura. |
| Race / idempotência | Chaves únicas por usuário/request, revisão do rascunho e mensagem recebida. Fences de transação/lease do executor; autorização e fronteira de rede persistidas. Casos importados com commit atômico e versões. Incerto nunca é retry de envio. Cancelar depois da fronteira não garante interromper a rede. |
| Isolamento / minimização | Tokens vinculados ao proprietário; conta e conteúdo não inferidos por domínio. Apenas conversas conhecidas, sem anexos; ambiguidades não importam corpo. Casos comerciais exportados explicitamente, sem acessar chats externos. |
| Dependências | requirements.lock com cryptography 50.0.2. pip-audit: zero vulnerabilidades conhecidas. npm audit, incluindo dev: zero vulnerabilidades conhecidas. Resultado temporal; reauditar antes do deploy. |
| Administrativo / menor privilégio | Nenhum painel administrativo novo, nenhuma elevação de papel. OAuth solicita send+readonly, sem modificar/excluir a caixa. Permissões operacionais mínimas e defaults desligados. |

## Riscos residuais e condição de liberação externa

Gmail real, consentimento/PKCE do cliente cadastrado, refresh/revogação reais, limites do provedor, verificação OAuth, SPF/DKIM/DMARC, reputação do remetente e requisitos por jurisdição precisam ser homologados pelo responsável. O cadastro de revisão não certifica legalidade nem entrega. Nenhuma mensagem real foi enviada.

Sincronização recupera somente histórico limitado de threads conhecidas; falha/ambiguidade não pode ser apresentada como caixa integralmente sincronizada. Conteúdo atribuído a uma conversa não é prova criptográfica da identidade humana. Uma solicitação de remoção é tratada conservadoramente com supressão.

Código anterior de pesquisa, automação e autenticação é preservado conforme comparação/regressão; isso não equivale a uma nova auditoria exaustiva de toda a base. Produção, Docker, PostgreSQL, navegadores diferentes de Chrome e dispositivos físicos não foram validados nesta execução.
