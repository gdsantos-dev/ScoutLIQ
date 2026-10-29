# Security Gate ORLIQ — primeira fatia 1.33

Revisão local de código, migração e testes desta entrega. Não é homologação de infraestrutura, pentest externo ou garantia de ausência de vulnerabilidades. Não houve deploy, envio real, alteração de conta pessoal ou migração operacional.

| Área | Controle/evidência e limite |
|---|---|
| Secrets / ambiente / frontend | Configuração por ambiente; pacotes excluem .env, DB, logs, runtime e node_modules. Ledger não grava tokens de provedor, URLs ou conteúdo externo. Chave pública de mapa da base requer restrição por origem. Nenhum OAuth real foi criado. |
| Autenticação / sessões / senhas | Argon2, sessão expirada/revogável e usuário ativo reutilizados. Bootstrap único antes dos filhos. Regressão de autenticação preservada. |
| Autorização / BOLA / IDOR / Broken Access Control | Todas as rotas de rotina usam proprietário autenticado; outras contas recebem 404. Trabalhador verifica conta ativa e recursos próprios. Endpoint público de saúde só expõe disponibilidade. |
| Mass assignment / privilege escalation | DTO específico extra=forbid, limites server-side, versões otimistas; API não aceita owner_id/role/plano/preço/ID de usuário. Teste rejeita campo privilegiado. |
| SQL injection / NoSQL | ORM parametrizado e nomes estáticos; nenhum filtro/SQL do usuário é executado. Não há banco NoSQL neste incremento. |
| CSRF / CORS / cookies / HTTPS | Mutações exigem sessão + CSRF; proteção de Origin/middleware existente preservada. Cookies/headers de produção continuam dependentes da origem HTTPS correta no host; teste local não comprova TLS real. |
| XSS / prompt injection | React escapa nomes/motivos/histórico; não se renderiza HTML externo novo. Conteúdo externo não vira instrução, comando ou permissão. LLM não implementado nesta fatia. |
| SSRF / redirects | Investigador existente conserva validação de destino/DNS/redirects e timeouts; instrumentação envolve a chamada, sem removê-los. Sem destino arbitrário de shell ou novo resolvedor. |
| Rate limiting / brute force / abuso | Limitadores existentes + configuração 20/min e controle 30/min por conta; cotas persistentes globais, por rotina e adapter, finitude de páginas/candidatas/investigações/prazo. Controles HTTP em memória não são proteção distribuída; deploy usa um processo web. |
| Concorrência / idempotência | UPDATE condicional no ResearchExecutor, token/lease, slot único por rotina/data e request_key determinístico; efeitos CRM sob mesmo fence. Duas operações concorrentes disputam cota atomicamente antes da chamada. Releitura externa após falha é possível; efeito duplicado confirmado não é permitido. |
| Pause / cancel / opt-out | Pausa/cancelamento invalidam trabalho apropriado e bloqueiam retomada por filho. Recusa e política por destinatário preservadas; investigação não autoriza contato. Excluir pesquisa cancela filhos. |
| Erros / logs / dados comerciais | Motivos seguros, sem stack trace de erro do worker na resposta; logs de supervisor sem credenciais. Consulta privada de consumo mostra totais globais compartilhados, sem lista de outras contas/leads. |
| Headers / CSP / clickjacking / MIME | Middleware existente preservado, sem relaxar CSP/origens. Automações não adiciona scripts externos. |
| Uploads / traversal / desserialização / command injection | Nenhum upload novo. Supervisor usa argumentos fixos sem shell. JSON limitado por schema; sem eval. Aplicador de PATCH valida caminhos e hashes antes de escrever. Bootstrap rejeita symlinks nos caminhos fixos do banco. |
| Menor privilégio / volume | Bootstrap Docker root restrito à posse dos caminhos conhecidos; abandona UID/GID/grupos antes de migrações/web/worker. Validado por inspeção; permissões reais do container/mount ainda não homologadas. |
| Dependências | Lockfiles preservados (frontend só versão do produto). npm audit e pip-audit consultados nesta entrega: nenhum alerta conhecido retornado. Isso não substitui revisão futura. |
| Histórico / retenção / exclusão | Migração roundtrip conserva registros centrais; novas configurações registram antes/depois. Histórico da rotina é removido com a pesquisa; ledger sem vínculo continua por conta. Não há limpeza automática de histórico nem retenção regulatória inventada. |
| Pagamentos / exportações / webhooks / admin | Fluxos existentes inalterados; nenhuma permissão administrativa nova. OAuth/outbox/webhooks comerciais ainda não iniciados. Identificadores de exportação e idempotência financeira preservados pela regressão. |

## Restrições para publicação

Homologar Docker/Railway, volume, UID, reinícios, fonte real, origem HTTPS, domínio/cookies, backup/restauração e cotas de contrato. Consultar novamente vulnerabilidades antes de uma publicação futura. Não usar modo demo/teste ou host de QA em produção. O sucesso local desta fatia não habilita Gmail, WhatsApp, PostgreSQL distribuído nem operação comercial sem revisão.
