# Revisão de segurança da entrega 1.32

Revisão do código alterado e testes locais, sem deploy nem alegação de auditoria externa. As proteções de autenticação, pesquisa web, mensagens e integrações da v1.31 foram preservadas. A revisão é proporcional às novas rotas e à execução durável.

| Área | Evidência e decisão |
|---|---|
| Secrets e ambiente | Arquivos de runtime, bancos, `.env`, dependências instaladas e artefatos não entram no FULL/PATCH. `.env.example` contém apenas configuração de exemplo. Não foi lido ou migrado o banco pessoal. |
| Autenticação, cookies, tokens e brute force | `current_user` continua exigindo sessão válida e conta ativa; hash de senha e expiração, cookies HttpOnly/SameSite/Secure conforme produção permanecem no fluxo existente. Rate limiting de autenticação e recuperação é coberto pela regressão. |
| Autorização, IDOR/BOLA e administração | Toda busca é consultada por ID e proprietário. Revisão exige lead da conta. Resultados validam proprietário antes da serialização. Worker confere usuário ativo e vínculo do lead/lote. Testes tentam ler, cancelar, salvar e revisar objetos de outra conta. Sem rota administrativa nova. |
| Mass assignment e escalada | DTOs recusam campos extras. `user_id`, estado, orçamento, leases, deadlines e IDs de lote são definidos pelo servidor. A revisão aceita somente autonomia, operação, modelo comercial, porte, natureza da entidade e motivo; exige a versão atual e não altera papel, preço, plano ou opt-out. |
| SQL/NoSQL injection | SQLAlchemy parametrizado; migração parametriza snapshot/ID. Sem banco NoSQL nem encaminhamento de operadores arbitrários. |
| XSS | Texto, motivo, nomes e páginas de origem são renderizados pelo escape React; não há `dangerouslySetInnerHTML` novo. Conteúdo remoto permanece dado, nunca instrução. |
| CSRF e CORS | Novas mutações usam a sessão/CSRF existente; origem divergente é recusada. Teste com CSRF inválido. Sem wildcard de credenciais nem CORS novo. |
| Input e abuso | Texto limitado, enums e target 25/50/75/100; até 4 setores e 3 buscas abertas. Limites persistentes de coleta, investigação, prazo e retry; intervalos e orçamento global do executor sobrevivem a reinício. Interpretação/start têm limites adicionais por usuário. |
| SSRF e destinos | Busca recebe setor/território, não URL de provedor. Investigação reutiliza WebsiteResearcher e suas validações de DNS/IP/redirect. Nenhuma ferramenta de shell/eval ou desserialização insegura foi adicionada. |
| Concorrência e idempotência | Chave única por usuário/pedido; lease condicional e token antes da gravação. Cursor e efeitos são comprometidos na mesma transação. Deduplicação ocorre antes da investigação. Resposta de tarefa expirada/cancelada não é aplicada. |
| Logs e erros | Exceções remotas não são persistidas literalmente; mensagem pública é genérica. Justificativas privadas ficam no histórico da própria conta. Não há stack trace novo para produção. |
| Upload, arquivos e path traversal | Nenhum upload novo. Aplicador de patch valida caminhos, hashes e conflitos antes de escrever, conserva runtime e cria backup. |
| Headers e HTTPS | CSP, frame-ancestors, X-Frame-Options, nosniff, Referrer-Policy e HSTS de produção permanecem. HTTPS real depende do host; não foi homologado nesta execução local. |
| Pagamentos, webhooks e exportações | Sem alteração em cobrança ou webhooks. Identificadores e proteção de duplicidade da exportação do ecossistema preservados; apenas a versão de origem é atualizada. |
| Privacidade | Sem dados de outras contas/chats, enriquecimento pago novo, envio real ou coleta de dados pessoais extras. Fixtures usam entidades e credenciais sintéticas identificadas como QA. |
| Dependências | Nenhuma biblioteca nova. Resultados de `npm audit` e `pip-audit` registrados no relatório de validação; dependências de runtime fixadas no lock existente. |

## Limites da revisão

Não equivale a homologação de PostgreSQL, Docker/Railway, TLS, provedores reais, credenciais de produção, supervisão do worker ou dispositivos físicos. O rate limiter HTTP continua em memória por processo, como na base; o orçamento de trabalho pesado é persistente por banco. Para múltiplas réplicas web, revisar limitação distribuída antes de deploy. Nenhuma alteração de infraestrutura foi aplicada.
