# v1.38-dev em integração — relatório final local

Data: 23/10/2026. Designação técnica: 1.38.0-dev. Não é release homologada nem implantação de produção.

## Base, conflitos e estado do repositório

Integração em `work/v1.38-dev/ScoutLIQ`, extraída do FULL v1.37.0. A pasta `work/v1.37.0/ScoutLIQ` foi preservada; os seus 447 fontes continuam com os hashes do manifesto original. A raiz do workspace contém a instalação histórica, não a v1.37; não foi usada como base nem sobrescrita.

- FULL v1.37 SHA256: `4e7848fe58ade25bf96b87be0f16dbdb5f8086a9105c72dcf7e0367eb3b8b687`.
- PATCH recebido SHA256: `eb30ef708d243198d38138f6f9a057cc64ecfc3e071bdcb3b0f81adef3903636`.
- DEV-OVERLAY-MANIFEST.json: seis arquivos modificados e oito adicionados. Todos os hashes do conteúdo recebido e dos originais conferidos antes de aplicar. Nenhum conflito com a base v1.37.
- Git no início e no fim: branch `master` sem commits; não há último commit. Os fontes existentes e `work/` são não rastreados. Nenhum commit, staging ou mudança de branch foi feito. O Git avisa falta de permissão ao enumerar a pasta histórica `.test-tmp-final-release`; ela não foi alterada e não impede verificar os fontes usados nesta integração.

O manifesto do overlay recebido permanece como proveniência histórica. Correções feitas nesta integração estão no manifesto atual e em [INTEGRATION-CHANGES-v1.38-dev.json](INTEGRATION-CHANGES-v1.38-dev.json); não se espera que seus hashes finais coincidam com o protótipo recebido.

## Implementação integrada

Em Gerenciar → Negociações → Absorver pesquisa, o operador cola ou abre JSON de 1–50 empresas. A prévia persistida distingue elegíveis, pendentes e duplicados. Confirmação explícita importa apenas elegíveis para o Lead canônico do Radar; mantém proveniência em LeadActivity, vínculo AbsorptionItem.lead_id e histórico do lote. Repetições retornam o recibo, sem recriar Leads.

Não existe outro CRM, score ou worker. `scoring.py`, `commercial_fit.py`, `providers.py`, `research_worker.py`, `search_intent.py` e `smart_search.py` permanecem idênticos à base. Website desconhecido e alegações externas não viram diagnósticos ou evidências confirmadas. Não há investigação, envio, abordagem ou chamada a provedor no fluxo de Absorção.

### Arquivos funcionais

| Criados | Modificados |
|---|---|
| backend/absorption.py; backend/absorption_models.py | backend/main.py: inclusão do router |
| frontend/src/components/AbsorptionDialog.tsx; absorption-dialog.css | frontend/src/App.tsx; pages/Pipeline.tsx: entrada e atualização do estado canônico |
| migrations/versions/028_absorption_staging.py | migrations/env.py: registro do modelo |
| tests/test_absorption.py; tests/test_absorption_migration.py; frontend/e2e/absorption.spec.ts | tests/conftest.py; tests/test_location_migration.py: limpeza/isolamento das novas tabelas |
| scripts/validate_browser_v138.py; scripts/package_integration_v138.py | package.json/lock, About, Settings e ecosystemBridge: somente identificação 1.38.0-dev |

README, contrato, instalação, mapa da próxima etapa, relatório e evidências também acompanham a integração. Não foram removidos fontes da base. Nenhuma dependência nova; o lockfile só recebeu a versão do projeto. Dependências locais já instaladas da v1.37 foram reutilizadas para build/testes; não foi executado novo npm ci nem auditoria online de dependências nesta etapa sem deploy.

## Problemas encontrados e corrigidos

1. A unicidade da chave de prévia não tinha recuperação de corrida; confirmações de lotes diferentes também podiam ler a mesma ausência de Lead. Uma atualização neutra da linha do usuário serializa prévia/commit no banco, antes de reconsultar chave, cotas e duplicatas. O claim e a criação do Lead continuam na mesma transação. Não modifica permissões ou perfil.
2. A UI gerava outro UUID a cada tentativa. Agora reutiliza a chave enquanto o conteúdo não muda, inclusive quando a resposta se perde depois de persistir.
3. Uma linha incompleta podia impedir uma linha completa posterior de ser absorvida. Somente registros elegíveis viram âncoras de dedupe no staging da prévia.
4. Categoria/cidade com um caractere passavam pela elegibilidade e falhavam no LeadInput durante o commit. Agora ficam pendentes, preservando o contrato canônico.
5. Telefone compartilhado podia fundir filiais com endereços diferentes. Endereços divergentes e coordenadas afastadas impedem esse atalho por telefone; deduplicação avançada permanece fora desta etapa.
6. Histórico com falha era silencioso e leitura de arquivo não tratava erro. Ambos agora apresentam estado de erro; os campos ficam desabilitados durante operações.
7. Migração 028 recusava downgrade apenas por itens; agora protege qualquer lote persistido. Normalizadas quebras de linha do env.py recebido.

## Migração e segurança

028 tem predecessora 027 e adiciona apenas absorption_batches/absorption_items, índices, chaves estrangeiras e restrições únicas. Revisões 001–027 não foram alteradas. Instalação limpa, ida/volta vazia 027↔028, igualdade de todas as tabelas anteriores, integridade/FKs e recusa de downgrade com staging foram testadas em cópias SQLite.

Sessão/CSRF/rate limiter e ORM existentes são reutilizados. Todo acesso de lote filtra user_id. DTOs recusam campos extras/privilegiados; IDs enviados não concedem acesso. URLs aceitam HTTP(S) sem credenciais, são dados armazenados e não destinos de requisições nesta integração. A UI usa texto React escapado. BodyLimit herdado limita requisições a 64 KiB, UI a 48 KB, além de 50 registros e campos limitados; há 200 lotes/conta e 12 prévias/12 confirmações por minuto/usuário. Rate limiting de requisições é local ao processo, como na base; não foi homologada topologia com múltiplas réplicas.

Não foram alterados autenticação, CORS, cookies, headers, configurações de produção, credenciais, outbox, OAuth ou políticas de destinatário. Não há uploads persistidos em disco: o JSON é validado e armazenado como staging. Nenhuma query é montada com entrada externa. Não se aplica um novo webhook, pagamento ou endpoint administrativo ao módulo.

## Testes realmente executados

| Verificação | Resultado | Evidência |
|---|---|---|
| Backend completo, `pytest tests -q` | **351 passaram**, 2 avisos, 237,68 s | [XML](evidence-v138/backend-full.xml), [log](evidence-v138/backend-full.txt) |
| Absorção/migração, subconjunto | **19 passaram**, não somar à suíte completa | [XML](evidence-v138/absorption-local.xml) |
| Unitários frontend finais | **23 passaram**, 7 arquivos | [XML](evidence-v138/frontend-unit-final.xml) |
| TypeScript dos E2E | Aprovado | [log](evidence-v138/e2e-types.txt) |
| Build final 1.38.0-dev | Aprovado | [log](evidence-v138/build-final.txt) |
| E2E novos de Absorção | **5 passaram** | [log](evidence-v138/e2e-absorption-release.txt) |
| Regressão E2E Busca Unificada | **9 passaram** | [log](evidence-v138/e2e-unified-search-release.txt) |
| Regressão E2E workflow/CRM | **5 passaram** | [log](evidence-v138/e2e-workflow-release.txt) |

Total de navegador: **19 E2E distintos**, em Chrome local com hosts/bancos separados. Não foi repetida toda a suíte visual de 53 E2E da v1.37; esses resultados históricos não contam como execução da integração. A rodada E2E precede apenas a troca dos rótulos de versão; build e unitários foram repetidos após essa troca, sem alterações funcionais posteriores.

Cobertura específica: prévia sem criar Lead; pendências; confirmação; duplicatas dentro/entre lotes e Leads; duas prévias simultâneas; commits simultâneos do mesmo lote e de lotes diferentes; rollback total após falha intermediária; CSRF/mass assignment/tamanho/rate limit; histórico e duas contas; ausência de OutreachDraft/OutboxMessage; migração limpa e preservação. Os E2E exercitam perda de resposta após persistência, arquivo JSON, erro/offline, reload, teclado/Escape/foco e 320/390 px. Axe não encontrou violações nas prévias mobile testadas. Capturas: [desktop](evidence-v138/absorption-desktop.png), [320 px](evidence-v138/absorption-320.png), [390 px](evidence-v138/absorption-390.png).

Tentativas iniciais de pytest não concluíram: antes do build, o backend herdado exigia dist/assets; outra execução ficou sem progresso no sandbox, e uma descoberta genérica percorreu dependências vinculadas. Foram interrompidas e substituídas pela execução explícita de tests com bancos temporários. Não contam como aprovações. Os avisos finais são deprecações Starlette/httpx e AnyIO e o aviso Vite do chunk MapLibre já existente; nenhuma asserção foi ignorada.

## Pacotes, reversão e prontidão

FULL e PATCH são de **desenvolvimento em integração**, gerados contra o hash exato da v1.37. O script package_integration_v138.py confere manifesto do FULL, aplicação em cópia descartável, dry-run sem escritas, recusa de conflito local, reaplicação recusada, backup e reversão dos fontes, preservando .env/banco sintéticos. O resultado final com hashes fica em release/INTEGRATION-VALIDATION.json e SHA256SUMS.txt no workspace. Pacotes excluem runtime, dependências, bancos e credenciais; .env.example permanece sem segredos reais.

**Pronta para a próxima fatia local de desenvolvimento**, com staging, contratos e testes disponíveis. **Não homologada para produção.** PostgreSQL, provedores reais, dispositivos físicos, leitores de tela humanos e produção não foram validados. Testes controlados não demonstram qualidade comercial ou conversão. Nenhum envio, deploy ou alteração de banco pessoal foi realizado.

CSV, edição individual, recuperação automática, investigação pós-importação, triagem e busca sem nicho estão somente mapeados em [NEXT-v1.38-dev.md](NEXT-v1.38-dev.md), incluindo riscos e critérios de aceite. A UI de Absorção ainda está somente em português; o staging não entra no export geral nem possui arquivamento. Não tratar essas capacidades como entregues.
