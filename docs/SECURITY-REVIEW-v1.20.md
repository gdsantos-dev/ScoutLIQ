# Revisão de segurança — 1.20.0

Revisão local da entrega, sem deploy. Comparação SHA-256 contra o ZIP fornecido: os 38 arquivos de backend e migrations são idênticos. A cadeia Alembic termina em `018`; não há migração nova. Isso preserva controles existentes, mas não substitui a homologação da infraestrutura de produção.

| Área | Evidência e alcance |
| --- | --- |
| Secrets e variáveis | Pacote por lista explícita de diretórios e arquivos. `.env`, bancos, logs, caches, dependências e artifacts excluídos. `.env.example` contém apenas configuração de exemplo. Credenciais E2E são deliberadamente de teste e não concedem acesso a produção. |
| Autenticação, sessão, cookies, brute force | Backend preservado: Argon2, sessões revogáveis, cookies HttpOnly/SameSite e Secure em produção. Testes de login, limites, troca/redefinição de senha, confirmação e expiração. |
| Autorização, IDOR/BOLA, privilégios | Recursos vinculados ao usuário no backend; testes de acesso cruzado a leads, sites, histórico, buscas, automações e campanhas. Navegação e comandos resolvem somente dados disponíveis para a sessão; não substituem autorização. |
| Mass assignment e validação | DTOs explícitos e validação no servidor preservados. Requests do frontend enviam campos específicos; IDs de entidades continuam sujeitos ao backend. |
| SQL / NoSQL / execução de comandos | ORM SQLAlchemy e filtros parametrizados preservados. Não foi adicionado banco NoSQL, shell executado por request, eval ou desserialização de código. |
| XSS e links | Texto renderizado por React; não há inserção de HTML de empresas/pesquisa. Links externos usam rel de isolamento e o backend restringe protocolos. |
| CSRF e CORS | Mutações continuam usando `X-CSRF-Token` e cookies same-origin. Testes de origem indevida e token ausente. Nenhuma abertura de CORS no redesign. |
| SSRF / redirecionamentos | Pesquisador existente com restrições de redes/portas/redirects. Testes de destinos locais. O frontend não ganha um proxy novo. |
| Rate limiting e ações caras | Limites existentes preservados. Operações de pesquisa são explícitas; processamento em lote avança serialmente pelo contrato existente. Não há polling contínuo novo. |
| Headers, HTTPS, logs e erros | Testes de modo produção verificam CSP, HSTS, cookies, documentação privada e headers. Sem stack traces adicionados à interface. HTTPS e headers no domínio real ainda exigem homologação. |
| Finanças e idempotência | Centavos inteiros, versionamento, request_id de pagamentos/custos e IDs de exportação preservados. Testes de concorrência, limite de saldo, reenvio e atribuição comercial. |
| Administração | API ORLIQ existente protegida por chave de servidor e testes próprios. Sem chave exposta no bundle ou menu administrativo novo. |
| Uploads, pagamentos externos, webhooks | Nenhum mecanismo novo. Recebimentos são registros comerciais, não transferência de dinheiro. Não existe upload nem integração de checkout/webhook neste redesign. |
| Dependências | `npm audit` e `pip-audit -r requirements.lock` executados: nenhuma vulnerabilidade conhecida reportada na consulta. O resultado vale para as versões e data da consulta, não é garantia permanente. |
| Atualização | Patch valida hashes antes de escrever, rejeita divergências, restringe caminhos ao diretório do projeto, faz backup e restaura cópias concluídas caso uma operação falhe. |

Não foram feitos pentest de infraestrutura, deploy, homologação PostgreSQL, execução Docker ou teste de envio real Brevo. A aplicação local usa dados sintéticos e SQLite isolado. Siga `SECURITY.md` e valide o domínio HTTPS, variáveis, réplicas/volume e backups antes da publicação.
