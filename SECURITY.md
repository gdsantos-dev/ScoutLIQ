# Segurança do ScoutLIQ

## Sistema e escopo

Aplicação privada de prospecção comercial da ORLIQ, publicada em HTTPS. Frontend React servido pelo mesmo processo FastAPI. SQLite persistido em volume privado. A V1 é uma operação privada com conta inicial criada pelo operador; não oferece uploads ou envio automático de mensagens comerciais. Há API administrativa ORLIQ protegida por chave de servidor, sem painel público nesta UI. A pesquisa web autenticada pode consultar páginas públicas para enriquecer um lead.

Esta política abrange `backend/`, `frontend/`, migrações, scripts e configuração de deploy. Não foram aprovadas exclusões de classes de vulnerabilidade. Material em `sources/` é referência sincronizada, somente leitura, e não integra a aplicação.

## Fronteiras e ameaças

O navegador e todo conteúdo de formulários são não confiáveis. Identificadores, valores financeiros, links, cookies e cabeçalhos recebidos devem ser validados. Credenciais, sessões, contatos e dados financeiros são ativos privados. O provedor do mapa recebe requisições de tiles do navegador (IP e área visualizada), mas não recebe os registros de leads pela aplicação.

O operador do Railway e quem tem acesso ao banco ou às variáveis de ambiente são administradores de infraestrutura. Os provedores de tiles e pacotes são dependências externas, não fontes de autorização. O banco não deve ser exposto em uma porta pública.

## Invariantes

- DTOs específicos rejeitam campos extras; usuário, demo, permissões e titularidade interna são definidos no servidor. Sites verificam a propriedade do registro e também da venda vinculada; um ID válido não concede acesso.
- Autorização no servidor em todas as rotas de negócio: cada consulta e mutação pertence ao usuário autenticado. A interface não é um controle de autorização.
- Senhas Argon2id; tokens de sessão aleatórios, apenas SHA-256 do token no banco; expiração em 12 horas. Trocar senha revoga todas as sessões.
- Cookie HttpOnly, SameSite=Strict e Secure em produção. CSRF vinculado à sessão em todas as mutações autenticadas; validação de Origin quando enviado. Login não aceita origem externa. Não habilitar CORS amplo.
- Secrets exclusivamente em variáveis de ambiente / `.env` ignorado pelo Git. Nenhuma chave deve usar prefixo `VITE_`.
- Validação Pydantic no backend, limites de tamanho, corpo de requisição limitado a 64 KiB e queries via ORM/parametrizadas.
- Links somente HTTP(S), sem credenciais embutidas; React escapa texto. Não usar `dangerouslySetInnerHTML` para dados de usuário. O pesquisador web é a única exceção de fetch server-side de URL de lead: restringe portas 80/443, resolve DNS antes da conexão, rejeita localhost/redes privadas/não globais, revalida redirects, limita timeout e corpo e nunca envia cookies ou credenciais do ScoutLIQ. A auditoria profunda herda essas proteções e só percorre até três páginas internas adicionais do mesmo domínio confirmado.
- CSP restrita, frame-ancestors none, nosniff, HSTS em produção e Permissions-Policy. `style-src 'unsafe-inline'` é necessário para estilos dinâmicos do mapa/gráfico; scripts inline não são permitidos. Workers blob são restritos ao uso do MapLibre.
- Valores em centavos inteiros. Venda e avanço a Fechado na mesma transação. Recebimento não excede o saldo; check e gravação serializados. Chaves de reenvio de pagamentos/custos e identificadores de exportação únicos. Conflito otimista protege edição de leads e sites.
- Limitação de login por conta e IP e de mutações por usuário. Um processo / uma réplica é obrigatório na V1. Não confiar em X-Forwarded-For arbitrário.
- Erros públicos sem stack trace nem valores sensíveis. Logs de erro não incluem payloads, senhas ou tokens. Não ativar debug em produção.
- Uploads não existem na V1. Adicionar upload exige validação de tipo real, tamanho, nomes, destino e autorização antes de disponibilizar a rota.

## Critérios de revisão

São relevantes acesso não autorizado a leads/finanças, sessão ou senha exposta, CSRF, XSS armazenado/refletido, SSRF, SQL injection, corrupção financeira, pagamentos duplicados, segredo no bundle/log, quebra de isolamento e esgotamento de recursos alcançável. Severidade depende de alcance, acesso exigido e impacto real. Ausência de reproduções não prova segurança. Não suprimir um achado apenas por esta documentação descrever um controle pretendido.

## Limitações conhecidas

- Sem MFA ou trilha de auditoria imutável. Cadastro, confirmação e recuperação por e-mail existem e dependem da configuração do backend; o script local de recuperação continua disponível ao operador. A API administrativa ORLIQ exige chave de servidor e possui testes de bloqueio e isolamento.
- Rate limit em memória reinicia com o processo. Não escalar horizontalmente sem store compartilhado. O IP do proxy pode ser compartilhado; limite por conta continua aplicado.
- Dados pessoais armazenados sem criptografia de campo. Proteger acesso ao volume, transporte HTTPS e backups; definir retenção e acesso operacional antes de inserir dados reais.
- SQLite: uma réplica e volume persistente. Migração PostgreSQL requer driver, revisão de migrações e testes do dialeto. Não assumir homologação PostgreSQL nesta versão.
- Exportação JSON não é backup completo (não contém usuários/sessões). O script SQLite usa backup consistente e verifica integridade.
- Mapas dependem de WebGL e de tiles públicos sem SLA. A lista continua disponível em falhas. Respeitar atribuição e política de uso do OpenStreetMap; trocar o provedor para escala comercial maior.
- Índice de oportunidade é uma regra operacional baseada em sinais informados, não garantia de venda nem validação automática de estabelecimento.
- Pesquisa web depende de páginas e índices públicos, pode ser bloqueada por sites e pode retornar candidatos ambíguos. O ScoutLIQ só grava o site no lead acima do limiar de confiança e preserva evidências; revisão humana continua válida.

Essas limitações são documentadas para avaliação do proprietário, não constituem exclusões ou aceitação automática de risco.

## Checklist antes de publicar

- [ ] Definir `APP_ENV=production` e `APP_ORIGIN=https://<domínio-exato>`.
- [ ] Configurar senha inicial exclusiva de 12+ caracteres e e-mail; remover a senha de bootstrap após criação da conta.
- [ ] Manter `.env` e backups fora do Git e fora da imagem Docker.
- [ ] `DEMO_SEED=false`; remover exemplos na interface antes da operação real.
- [ ] Montar volume em `/data`, `DATABASE_URL=sqlite:////data/scoutliq.db`, uma réplica e um worker.
- [ ] Verificar usuário de execução e permissão de escrita no volume, healthcheck e persistência após redeploy.
- [ ] Executar testes, build e auditoria atual de dependências; revisar avisos que não puderem ser resolvidos.
- [ ] Testar login, logout, CSRF, cookies Secure/HttpOnly/SameSite, origem e headers no domínio HTTPS final.
- [ ] Testar backup e restauração em cópia isolada; configurar rotina de backups fora do volume principal.
- [ ] Revisar acesso ao workspace Railway, retenção de logs, dados pessoais e permissões de operadores.
- [ ] Confirmar atribuição e adequação do serviço de tiles ao volume esperado.
- [ ] Fazer teste real: cadastrar lead, fechar venda, receber parcial, registrar custo e exportar.

## Relato responsável

Não publique credenciais, dados de clientes ou provas com dados reais. Encaminhe suspeitas de vulnerabilidade ao responsável pelo workspace ORLIQ por canal privado já acordado. Ainda não há endereço público de divulgação definido.

## Cadastro e recuperação de conta

- Contas novas só autenticam após confirmação de e-mail.
- Tokens de confirmação e redefinição são aleatórios, de uso único, têm expiração e são persistidos apenas como SHA-256.
- Redefinir a senha encerra todas as sessões existentes da conta.
- Solicitações de recuperação usam resposta genérica para não revelar se um e-mail está cadastrado.
- Cadastro, reenvio, login e recuperação possuem limitação de tentativas por IP/e-mail no processo web.
- Em produção, configure a Brevo apenas no backend. `BREVO_API_KEY` nunca é enviado ao frontend.
