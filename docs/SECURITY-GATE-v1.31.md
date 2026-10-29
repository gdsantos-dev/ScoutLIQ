# Revisão de segurança — ScoutLIQ 1.31

Revisão manual dos contratos alterados e testes locais. Não é pentest, scan exaustivo ou autorização de deploy. Escopo: migração 020; evidências, outreach, política de destinatário, executor; integração em main.py e interfaces afetadas. Sem novos serviços de envio ou LLM.

| Área | Resultado e limite |
| --- | --- |
| Secrets e ambiente | Nenhum token novo necessário. Configuração do worker no .env.example, carregada pelo backend. FULL/PATCH usam lista de inclusão e excluem .env, banco, auth sintética, logs e caches. Credenciais E2E existem somente como fixtures não produtivas. |
| Autenticação, sessões, cookies e brute force | current_user e sessões existentes preservados; cookies HttpOnly/SameSite=Strict e Secure em produção. Login e recuperação mantêm limites. Testes não desativam rate limiting; reutilizam sessão sintética. HTTPS real ainda precisa ser validado no domínio final. |
| Autorização, IDOR/BOLA e acesso administrativo | Propriedade de lead/filhos/política por usuário verificada no servidor; tarefas derivam usuário da fila. Worker revalida conta ativa e dono do lead antes do commit. GET de lote só devolve leads pertencentes à conta. Não há novo endpoint administrativo. |
| Mass assignment e escalada | DTOs explícitos extra=forbid; papéis, dono, status privilegiado e campos internos não são aceitos. Versões antigas de mutação retornam conflito. |
| SQL/NoSQL Injection | SQLAlchemy parametrizado, sem concatenação de entradas em SQL. Nenhum banco/filtro NoSQL adicionado. |
| XSS, URLs e SSRF | React renderiza conteúdo como texto; URL de fonte validada HTTP(S), sem credenciais. A ficha não busca a URL arbitrária. Worker reutiliza o pesquisador/provedor e suas validações SSRF existentes, testadas na suíte backend. Sem novo cliente HTTP. |
| CSRF e CORS | Mutações continuam exigindo sessão, token e Origin. Sem wildcard novo nem ampliação de CORS. |
| Rate limiting e abuso | Limites existentes de mutações/login; até 200 evidências e 50 drafts por lead. Worker limitado por intervalo global, orçamento persistente de tarefas e três tentativas. O rate limiter HTTP herdado é por processo: não é distribuído. Orçamento do worker não é teto de custo do provedor. |
| Concorrência e idempotência | Versionamento otimista de evidência/draft/política. Chave de preparação única e comparação de payload/estratégia. Claim atômico e token com lease impedem dois commits da tarefa; conclusão e efeitos no CRM na mesma transação. Leituras externas podem ser repetidas após falha. |
| Aprovação e opt-out | Hash inclui versões de política/evidências/lead, conteúdo, destinatário, idioma, canal e validade. Conteúdo aprovado não concede elegibilidade. Opt-out por destinatário normalizado bloqueia duplicatas na mesma conta/canal; sem inferência entre e-mail e telefone. Dispatch permanece fechado, sem adapter. |
| Inputs, uploads, execução e deserialização | Schemas tipados, limites de comprimento/listas e enumerações; sem upload novo, pickle, eval, comando shell com input ou redirecionador novo. |
| Logs e erros | Worker persiste mensagens genéricas e não registra exceções brutas de provedores. Histórico privado inclui justificativas e fatos necessários à auditoria. Erros HTTP seguem handlers existentes; não há stack trace de produção novo. |
| Headers e CSP | Middleware herdado preservado. CSP ainda contém unsafe-eval; necessidade do mapa não foi auditada integralmente. Não declarar CSP estrita. Clickjacking e MIME sniffing mantêm proteções existentes. |
| Dependências | Arquivos lock preservam versões da base. Resultado das consultas npm audit/pip-audit registrado no relatório de validação, sem afirmar ausência de vulnerabilidades desconhecidas. |
| Exposição, exportação e retenção | Exportação privada inclui evidências, drafts e políticas; hash de aprovação e user_id internos omitidos nesses registros. Política de destinatário é vinculada à conta e sobrevive à exclusão de um lead para evitar recontato indevido. Retenção automática e trilha imutável não implementadas. |
| Webhooks, pagamentos e finanças | Nenhum webhook/envio/cobrança novo. Finanças existentes preservadas. Outbox e deduplicação de webhooks continuam pré-requisitos da etapa de envio oficial. |
| IA e prompt injection | Geração determinística, identificada como tal; texto externo é dado. Não existe modelo autorizado a executar instruções do conteúdo coletado. |

## Antes de produção

Validar restauração de backup, origem final, HTTPS/cookies, permissões do arquivo/banco, retenção e supervisor do worker no mesmo volume persistente. Operação contínua em Railway, PostgreSQL, Docker e provedores reais não foi homologada localmente. Não distribuir SQLite por réplicas com arquivos independentes. Parar todos os executores antes de mudar entre worker/legacy.

## Etapa oficial Gmail e WhatsApp Business

Reutilizar OutreachDraft, RecipientPolicy e LeadActivity; não criar CRM paralelo. Implementar OAuth/tokens criptografados com escopos mínimos e revogação; adapter por canal; elegibilidade verificável por mercado/provedor; revalidação de hash imediatamente antes do envio; outbox idempotente com chave por draft/versão e estado de resultado incerto; webhooks autenticados e deduplicados; resposta/opt-out revogando pendências; recuperação e testes em sandbox do provedor. Homologação e autorização operacional precedem qualquer envio comercial real.
