# Revisão de segurança da V1 — 22/09/2026

Revisão local de implementação e testes. Não equivale à homologação do domínio de produção, que ainda não foi publicado.

| Área | Controle / evidência |
| --- | --- |
| Secrets / ambiente | `.env` ignorado; exemplo sem credenciais; empacotamento por lista explícita sem dados locais. Nenhum secret de integração no frontend. |
| Autenticação / sessões | Argon2id, cookie HttpOnly + SameSite Strict, Secure em produção, expiração 12h e revogação na troca de senha. Testes de produção isolada. |
| Autorização / IDOR / BOLA | Consultas por usuário; testes com outro proprietário para leads e Sites, inclusive vínculo de Site a venda alheia e exportação. |
| Broken Access Control / privilégio / mass assignment | DTOs com `extra=forbid`, campos de propriedade definidos no servidor. Sem endpoints de cadastro/admin público. |
| SQL Injection | SQLAlchemy parametrizado; SQL literal apenas para controle interno da transação e healthcheck. |
| NoSQL Injection | Não aplicável: nenhum banco ou filtro NoSQL. |
| XSS / URLs / SSRF / redirects | React escapa texto; URLs HTTP(S) sem credenciais. A pesquisa web valida DNS/IP público, bloqueia localhost/redes privadas, restringe 80/443, revalida redirects e limita tempo/tamanho. CSP sem scripts inline. |
| CSRF / CORS | Token vinculado à sessão em mutações; origem exata quando presente; CORS não habilitado. Testes de origem estrangeira e token ausente. |
| Rate limit / brute force | Login por conta e IP, mutações por usuário, exportação e troca de senha limitadas. Hash concorrente limitado a dois. Um worker obrigatório. |
| Validação / exposição | Campos, valores, datas e comprimento validados; limite de corpo 64 KiB; respostas não incluem hashes de senha/sessão. |
| Upload / deserialização / comandos | Upload ausente; sem eval ou execução de comandos com input; scripts operacionais locais não são rotas. |
| Headers / HTTPS | CSP, nosniff, frame-ancestors none / DENY, Permissions-Policy; HSTS e Secure testados em modo produção. HTTPS final pendente de deploy. |
| Logs / erros | Erros públicos sem stack/payload; logging apenas do tipo de falha interna. |
| Concorrência / idempotência | Recebimentos serializados e limitados ao saldo, chave de reenvio; custos idempotentes; export IDs estáveis; testes simultâneos e de conflitos. |
| Webhooks / pagamentos externos | Não aplicável: sem gateway nem webhooks; apenas registro comercial interno. |
| Dependências | Locks Python/JS, auditorias documentadas em VALIDATION.md. MapLibre atualizado após aviso de vulnerabilidade. |
| Infra / privilégio mínimo | Docker não-root; banco em volume privado. Permissões do volume e domínio ainda exigem validação no Railway. |

## Pendências antes de operação real

Executar o checklist de SECURITY.md no domínio HTTPS definitivo, comprovar persistência após redeploy e restauração do backup, configurar retenção/acesso a backups e revisar limites do provedor de tiles. Rate limit em memória não permite múltiplas réplicas; SQLite e ausência de MFA seguem documentados. PostgreSQL e imagem Docker ainda não foram homologados neste ambiente.
