# Absorção Inteligente — v1.38.2-dev

## Funcionalidades implementadas

A evolução usa exclusivamente o FULL v1.38.1-dev, SHA256 `2a92b87a7eb4c0d513698df05fc18dca7ac5e3d373d41a6a0d0b42bcb7879229`. A cópia de trabalho fica separada da instalação anterior. Não houve deploy, acesso a banco pessoal, chamadas comerciais reais ou alteração no Score 3.0.

- JSON preserva `/preview` e o contrato estrito anterior. O novo `/intake` permite erros individuais; recebe JSON, CSV e tabelas coladas. A interface usa `/parse` antes da persistência.
- CSV/TSV: UTF-8, BOM, campos entre aspas, quebras internas, vírgula/ponto e vírgula/tab/barra, decimais com ponto ou vírgula. Limites: 48 KB UTF-8, 50 empresas, 32 colunas, 4.000 caracteres por célula; o limite HTTP existente continua em 64 KB. Cabeçalhos desconhecidos, destinos repetidos e ausência de nome exigem revisão explícita. Colunas ignoradas continuam no original.
- Normalização reutilizável: espaços/caracteres de controle, país ISO, aliases inequívocos de categorias, domínio/URL, perfil Instagram e dígitos de telefone. Não inventa país no intake nem DDI. O endpoint legado conserva BR como default de compatibilidade.
- Correções persistidas com versão, motivo, antes/depois e original imutável. Campos privilegiados nunca são aceitos. Registros já absorvidos são editados pelo Radar, não pelo staging.
- Confirmação incremental: o lote permanece parcial enquanto houver pendências. Novas confirmações criam apenas os itens prontos e preservam os IDs anteriores. Replay da confirmação não duplica Leads.
- Identidade em três níveis: confirmado, possível e distinto. Nome/geografia/endereço/contatos/domínio/IDs da fonte são combinados; endereço ou coordenadas divergentes preservam filiais. Não há fusão destrutiva. Possíveis duplicatas admitem decisão justificada. “Atualizar lote” reavalia referências alteradas em outros lotes sem consulta externa.
- Recuperação explicitamente acionada: cache e registros do próprio usuário primeiro; fonte externa somente com a opção marcada. Resultados seguros completam somente campos obrigatórios faltantes. Ambiguidades viram sugestões com procedência, data e ID; o operador aceita, rejeita ou corrige. Nenhuma sugestão cria um Lead.

## Arquitetura e limites

`AbsorptionRecovery` é a única tabela nova, adicionada pela migração 029. O executor já existente reivindica tarefas de tipo `absorption`, após as filas anteriores, com a mesma exclusão global, lease, WorkAttempt e medição de operações HTTP. Não há worker ou pipeline de comunicação adicional.

Cada tarefa trata um registro. O estado guarda fila/versionamento, cursor, reservas, sequência e prazo. As requisições ocorrem fora da transação. Antes de reservar e antes de persistir, a aplicação verifica token do executor, usuário, job, prazo e versão do registro. Resultado tardio após correção/pausa/cancelamento não é aplicado. Interrupções não devolvem reservas possivelmente consumidas.

Limites: uma recuperação ativa por usuário, até 20 execuções por lote, prazo de 30 minutos sem extensão automática, 3 tentativas consecutivas por item; retries de 30 e 60 segundos. A reserva externa padrão é 20 por execução, configurável de 1 a 50, com teto acumulado de 50 por lote. Orçamentos diários do worker e do ledger de provedores continuam vigentes. Sem worker disponível, o estado fica na fila até expirar quando o worker voltar. Pausa preserva o prazo; uma pausa expirada precisa ser cancelada antes de novo pedido.

A consulta Geoapify usa as primitivas existentes de resolução administrativa e conversão de POIs. O limite administrativo é apenas filtro de `/v2/places`, com nome, categorias comerciais já suportadas e no máximo 5 candidatos. Somente um POI com nome, ID, cidade, país e coordenadas observados pode ser proposto. Não há geocodificação de centro de cidade promovida a coordenada comercial. Geocodificação usa o timeout existente limitado a 15 s; consulta de POIs usa 8 s e resposta de até 500 KB. Até duas reservas por registro; a reserva administrativa pode ser conservadoramente contabilizada mesmo com cache interno do provedor.

O contrato oficial de [Geoapify Places](https://apidocs.geoapify.com/docs/places/) prevê `name` e filtro `place`; o filtro de país está identificado como “coming soon” nessa documentação e não foi adotado. Não foram consumidas cotas reais.

A recuperação externa exige cidade e país informados para delimitação segura. Ausência desses campos pode ser resolvida por referências internas ou edição humana. OSM/demo não possuem adaptador de recuperação comercial confiável neste ciclo: o job informa a limitação e mantém a pendência, sem troca silenciosa de fonte. Consultas de nomes comuns e limite de 5 candidatos podem não encontrar o estabelecimento; isso não prova que ele inexiste.

O cache de candidatos usa `LocationCache` com namespace específico, usuário e configuração da fonte no hash, TTL de 1 hora e procedência preservada. Nada consulta provedores ao abrir a tela, listar histórico ou atualizar progresso. O orçamento mostrado é de reservas; o ledger existente mede operações HTTP efetivas.

## Lead, evidências e segurança

A confirmação reutiliza LeadInput, Lead, LeadActivity e os hooks comerciais existentes. `source_id=absorption:<item-id>` identifica a entrada canônica; os IDs originais permanecem no staging e na atividade de proveniência. A atividade guarda original, normalizado, correções, fonte e alegações marcadas como não verificadas. `website_status` continua `unknown`, `instagram_active` false e `in_pipeline` false. Nenhuma campanha, outbox, comunicação ou investigação começa automaticamente.

Autenticação e CSRF existentes cobrem todas as mutações. Consultas de lote/item/job/cache são limitadas ao usuário; locks por usuário e versões evitam gravações concorrentes. Schemas específicos e allowlists bloqueiam mass assignment. ORM/SQL parametrizado, sem NoSQL, eval, shell ou execução de arquivo recebido. URLs externas são armazenadas/normalizadas e nunca usadas como destinos da recuperação. Apenas o adaptador configurado do backend faz rede. Erros externos são mensagens estáveis, sem credenciais, URL de requisição ou stack trace. React escapa texto e o original é exibido como texto. Arquivos são lidos em memória; não há endpoint de upload para filesystem.

Headers, CORS, autenticação/senhas, cookies/tokens, rate limiting, limites de corpo, dependências, webhooks e APIs administrativas existentes foram preservados. Não há novas dependências ou permissões de provedor. A revisão local não equivale a pentest, auditoria externa atualizada de vulnerabilidades, homologação PostgreSQL, HTTPS público ou produção.

## Migração e reversão

029 acrescenta versões, ordem dos lotes, hash de entrada imutável, originais, histórico, problemas, decisões, candidatos e tabela de jobs. Para registros 028, original recebe payload anterior; hash de entrada recebe hash anterior. Leads e tabelas comerciais não são reescritos.

Downgrade é recusado se existirem jobs, correções, novas versões de itens ou diferenças entre original e normalizado. Nunca force a perda de auditoria. Em SQLite, a remoção de colunas usa ALTER TABLE nativo para evitar reconstrução de tabelas-pai com cascata. Validação local usa SQLite com suporte a DROP COLUMN; para banco antigo ou PostgreSQL, validar primeiro uma cópia. Rollback completo após uso da 029 exige restaurar um backup consistente de código e banco; rollback apenas de fontes não reverte dados.

## Arquivos principais

Criados: `backend/absorption_input.py`, `backend/absorption_identity.py`, `backend/absorption_recovery.py`, `migrations/versions/029_absorption_recovery.py`, testes inteligentes/migração/E2E e scripts `package_absorption_v1382.py`/`validate_browser_v1382.py`.

Alterados: `backend/absorption.py`, `backend/absorption_models.py`, despacho do worker, `AbsorptionDialog.tsx`/CSS, fixtures/testes de compatibilidade, versões do frontend e documentação. O manifesto do PATCH enumera todas as diferenças com SHA256 anterior/posterior. Migrações até 028, Score, qualificação, motores de descoberta, provedores, App e Pipeline são comparados à base na embalagem.
