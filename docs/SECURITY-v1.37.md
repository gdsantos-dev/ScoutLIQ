# Segurança — v1.37

Revisão proporcional das mudanças da versão; não é homologação de produção nem
scan exaustivo independente. Não houve deploy, alteração de credenciais pessoais,
envio comercial real ou mudança de permissões externas.

| Área | Tratamento e limite |
|---|---|
| Secrets e ambiente | Apenas `.env.example` foi alterado. Chaves continuam no backend. Fixture usa credenciais sintéticas locais e `EMAIL_MODE=memory`. Empacotamento usa allowlist e exclui banco, `.env`, logs operacionais e runtime. Evidências selecionadas contêm apenas dados sintéticos. |
| Autenticação | Novos endpoints exigem `current_user`; teste sem sessão retorna 401. Autenticação e expiração/revogação existentes preservadas. |
| Autorização / IDOR / BOLA | Consulta de job e idempotência incluem usuário. Revisão exige propriedade do Lead. Resultados canônicos são filtrados pelo dono antes de serializar. Não confiar na UI para esta autorização. |
| Mass assignment / privilégios | Launch e critérios usam schemas `extra=forbid`. Critérios não aceitam `user_id`, `market`, privilégios nem IDs de empresas. Testes negativos acrescentados. |
| SQL / NoSQL | SQLAlchemy com expressões parametrizadas; nenhuma concatenação SQL nova. Nenhum banco NoSQL ou operador fornecido pelo usuário foi introduzido. |
| XSS | Texto de catálogo, evidência e justificativa renderizado pelo React. Nenhum HTML de terceiros injetado. Estado de localização em localStorage validado antes de renderizar e resolvido novamente no backend. |
| CSRF / CORS | Proteções herdadas preservadas. Teste executado inicialmente em `127.0.0.1` foi recusado porque a origem configurada era `localhost`; corrigida a URL de teste, sem relaxar a proteção. |
| Rate limit / abuso / custos | Launch 6/minuto e catálogo 30/minuto por usuário; debounce no cliente não substitui servidor. Modelo desativado por padrão e condicionado a política/configuração/orçamento existentes. Revisão comercial limitada a 30/minuto. Catálogo possui cache por usuário e orçamento durável (padrões 300 chamadas/dia e 100/usuário), com reserva atômica antes da rede; falhas/interrupções consomem reserva. |
| Validação geográfica / SSRF | Seleção por ID e resolução no catálogo conhecido. Não aceita URL de usuário no fluxo novo; ID restrito impede injeção de filtros Geoapify. Coordenadas finitas/pareadas e bbox ordenada. Não busca URLs arbitrárias nem troca fronteira por raio. |
| Idempotência / concorrência | Restrição única por usuário/chave; hash compara payload. Colisão faz rollback e relê vencedor, sem duplicar job. Os testes injetam a disputa após a leitura inicial; não substituem teste de carga distribuída. |
| Revisão humana | Campos permitidos e versão exigida. Alterações exigem motivo de 10–500 caracteres. Confirmar avaliação atual só aceita os mesmos valores, reutiliza justificativa e registra interação explícita sem elevar fatos desconhecidos. Endpoint existente mantém atividade e reclassificação. Controle de versão obsoleta coberto por testes herdados. |
| Logs / erros / dados | Mensagens novas de indisponibilidade não incluem credenciais, stack ou payload de provedor. Erros de catálogo propagam mensagem segura. Relatórios usam dados sintéticos; nenhuma alegação de dados comerciais reais. |
| Upload / caminhos / comandos | Nenhum upload, comando remoto ou desserialização executável adicionado. Empacotamento verifica caminhos e hashes contra o FULL autorizado, com dry run, conflito, backup e reversão em cópia descartável. |
| Headers / HTTPS / cookies | Infraestrutura herdada; não modificada para contornar testes. HTTPS, proxy, cookies em domínio real e PostgreSQL não homologados nesta execução. |
| Webhooks / outreach / pagamentos | Nenhuma expansão de escopos, webhook, envio, pagamento ou motor de comunicação. Requisitos e bloqueios existentes preservados. |
| Dependências | Nenhuma dependência adicionada. npm ci executado em diretório limpo; lockfile atualizado dentro dos intervalos permitidos para corrigir três alertas de desenvolvimento. npm audit final e pip-audit de requirements.lock: zero vulnerabilidades conhecidas em 22/10/2026. Isso não prova ausência de vulnerabilidades não catalogadas. |
| Endpoints administrativos | Nenhuma nova rota administrativa ou bypass introduzido. |

## Validação da área do mapa

Área do mapa usa schema exclusivo: bbox finita/ordenada, raio derivado de até
25 km, polígono simples de 3–32 pontos, envelope consistente e rejeição de campos
extras. A localização administrativa e a área não podem coexistir no pedido.
O modelo semântico não fornece geometria. O recorte usa a persistência existente;
o adaptador Geoapify recusa resultados sem cidade e país observados. Mudanças na
geometria com a mesma chave retornam conflito. Testes controlados verificam esses
contratos, inclusive a recusa de coleta quando o provedor não tem capacidade.

## Isolamento e preservação

Cache geográfico possui FK de usuário e chave derivada também da identidade/configuração. Dados de outra conta não viram resultado do solicitante. O gate de catálogo usa UPDATE transacional independente, sem interferir no token/lease do worker. As reservas são gravadas no ledger existente.

O adaptador de consultas antigas não aceita campos privilegiados. Desativar/excluir monitor cancela jobs associados e invalida retorno em trânsito; sync_results confere propriedade, conta ativa, fingerprint da consulta e habilitação do monitor antes de atualizar snapshot. Recuperação mantém o mesmo job e contabiliza tentativas.

A migração 027 acrescenta apenas cache/gate. Versões históricas de migração não foram alteradas. Upgrade/downgrade foi exercitado em cópia do banco com igualdade de todas as tabelas anteriores, integridade SQLite e FKs. Score, CommercialFit e outreach mantêm hash da base. Adaptações necessárias do worker estão enumeradas em SEARCH-COMPATIBILITY-v1.37.md e fixadas por hash.

## Limites da revisão

Revisão proporcional e regressão local, sem scanner externo independente, teste de intrusão, deploy ou homologação distribuída. HTTPS/cookies/proxy/domínio, PostgreSQL e configuração de provedores reais exigem validação no destino. Rate limiting herdado de login é por processo; escalar réplicas requer proteção compartilhada na infraestrutura. Nenhum pagamento, webhook, escopo OAuth ou envio real foi autorizado por esta versão.
