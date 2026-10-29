# Revisão de segurança da entrega v1.36

Revisão proporcional a uma alteração de frontend, com backend preservado e regressão local. Não é certificação nem auditoria de produção. Não houve deploy.

| Área | Resultado / fronteira |
|---|---|
| Secrets, env, logs, dados | Pacote de fontes por allowlist; exclui `.env` real, bancos, caches, logs e dependências instaladas. Somente `.env.example`. Evidências visuais usam dados sintéticos. Nenhuma credencial movida ao frontend. |
| Autenticação, senha, sessões, cookies, revogação | Backend v1.35 intacto; testes de contas/produção executados. HTTPS/Secure dependem da configuração real e não foram homologados em loopback HTTP. |
| Autorização, IDOR/BOLA, escalada, mass assignment, admin | Rotas/DTOs intactos; testes de isolamento e operações sensíveis da regressão executados. Esconder formulário não concede permissão; servidor revalida toda ação. |
| SQL / NoSQL | ORM e schemas existentes preservados. Nenhum SQL, filtro de banco ou datastore novo; NoSQL não introduzido. |
| XSS e entradas externas | JSX continua escapando texto; casos importados com HTML permanecem texto no E2E. Sem nova renderização HTML não confiável. Links e serviços existentes preservados. |
| CSRF / CORS / rate limit / brute force | Cliente continua enviando CSRF pelas APIs existentes. Políticas do servidor intactas. Testes isolados em vez de reduzir limites. |
| SSRF / redirects / uploads / comandos | Nenhuma superfície nova. Backend e validações existentes preservados. Importações revisadas continuam validadas pelo serviço. |
| Headers / CSP / erros | Middleware existente preservado; falhas HTTP, offline e expiração verificadas no navegador. Não mostrar stack trace na UI. |
| Tokens OAuth / webhooks | Credenciais protegidas no servidor; nenhuma mudança de escopo. Gmail real não homologado; webhook WhatsApp não implementado nesta camada. |
| Idempotência / duplicidade / comunicação | Ledger e guardas intactos. E2E com provedor controlado e worker real local. Uma rodada residual foi reagendada pelo limite de intervalo; proteção mantida. |
| Dependências | Nenhuma dependência adicionada. npm audit (incluindo dev) e pip-audit do requirements.lock: zero vulnerabilidades conhecidas na consulta de 19/10/2026. Isso não garante ausência de vulnerabilidades. |
| Produção | Deploy, domínio, TLS, configuração CORS/cookies, permissões de volume e contas de provedores exigem validação no ambiente de destino. Nenhuma homologação externa atribuída a estes testes. |

Regressão: 265 testes backend, incluindo autenticação, objetos de outros usuários, segurança de produção, aprendizado, comunicação e migrações. Ver VALIDATION-v1.36.md para escopo e resultados de navegador. FULL/PATCH verificam hashes e recusam conflitos/reaplicação, preservando arquivos de runtime na instalação isolada.
