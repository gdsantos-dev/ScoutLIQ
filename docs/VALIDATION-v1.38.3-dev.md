# Validação — v1.38.3-dev

Entrega de desenvolvimento implementada e validada localmente em Windows, SQLite e Chrome headless. Base integrada v1.38.2-dev conferida por hash, sem divergências locais. Nenhum deploy, banco pessoal, envio real ou cota de provedor utilizada.

## Resultado

| Verificação | Resultado |
|---|---|
| Regressão backend integral | **440 aprovados** |
| Investigação e migração 030, rodada focada | **28 aprovados**, sobreposição com a regressão; não somar |
| Frontend unitário | **24 aprovados**, 7 arquivos |
| Build e TypeScript | Aprovados; bundle de mapa ainda emite o aviso histórico de tamanho |
| E2E histórico, 13 suítes | **65 aprovados** |
| E2E novo, desktop e mobile | **3 aprovados** |
| Engines e migrações protegidos | **37 arquivos idênticos** à base |
| Upgrade 029→030 | Preservação de colunas e registros, defaults desligados, FK e integridade aprovados |
| Downgrade | Recusa de perda de fila e preferências aprovada |

A regressão backend integral foi repetida sobre o código final. As suítes históricas de navegador passaram antes do último ajuste restrito ao seletor/atualização do lote, à seleção entre filtros e ao tamanho visual das caixas de seleção; build, tipagem e E2E de investigação foram repetidos sobre esse ajuste. A suíte de aprendizado foi repetida após a correção de data descrita abaixo. A lista final consolida essas execuções; não representa uma única rodada simultânea. Os resultados e durações estão em [VALIDATION.json](qa-v1.38.3-dev/VALIDATION.json).

## Cobertura da missão

| Cenários | Evidência |
|---|---|
| Solicitação manual, 100 empresas, lote ativo, ordem, restart e deduplicação | `test_manual_progressive*`, `test_100_queue*`, `test_concurrent_enqueue*`, `test_legacy_batch*` |
| Preferências e entradas Busca/Absorção | `test_default_off*`, `test_unified_discovery*`, E2E de preferências e Absorção |
| Cache e conferência sem rede | `test_economic_and_cache*`, `test_recent_good_site*` |
| Profundidade seletiva, sem site, dados insuficientes | `test_selective_depth*` e conferência econômica |
| LeadResearch, Score, histórico e ausência de comunicação | `test_manual_progressive*`, `test_fetch_failure*`; testes canônicos preservados |
| Timeout, limites diários, reserva e resultado parcial | `test_timeout*`, `test_daily_cap*`, `test_budget_reservation*`, `test_daily_network_budget*` |
| Pausa, retomada, cancelamento, token e resposta tardia | `test_control_revokes*`, `test_pause_during_network*`, `test_expired_lease*` |
| Exclusão durante consulta e isolamento | `test_deleted_lead*`, `test_cross_user*` |
| CSRF, DTO fechado e transação de ingresso | `test_csrf_and_automatic_ingress_transaction_rollback`, isolamento e regressão de segurança |
| Migração 029 preservada | `test_investigation_migration.py`, testes históricos 027/028/029 |
| Desktop/mobile e acessibilidade | `investigation.spec.ts`, `redesign.spec.ts`, capturas e verificações Axe do novo fluxo |

## Ajustes durante a validação

A primeira rodada encontrou duas comparações históricas que incluíam as novas colunas da 030 ao verificar schemas antigos. Os testes passaram a congelar a revisão correspondente antes do snapshot, preservando a comparação integral dos dados daquela revisão. A migração 030 possui teste próprio por coluna/tabela. Uma fixture da Busca exigia modo worker, e o teste mobile precisava distinguir dois anúncios `role=status`; ambos foram corrigidos. A regressão de navegador também encontrou um defeito já presente na base (arquivo CommercialLearning.tsx idêntico por SHA256): entre a meia-noite UTC e a virada de data em São Paulo, o formulário sugeria uma revisão futura. O formulário passou a reutilizar inputDate, formatador de calendário do produto, inclusive nos limites dos campos. A fixture de aprendizado usa o mesmo calendário. Um teste com relógio congelado em 25/10 às 01:30 UTC confirma 24/10 no calendário de São Paulo. A validação futura do backend foi preservada. As rodadas finais citadas acima passaram.

## Segurança e dependências

Autenticação, CSRF, autorização por objeto, DTOs fechados, rate limiting, transação, deduplicação concorrente, lease e reserva antes de rede foram exercitados. O pesquisador SSRF e seus testes foram preservados. Nenhuma credencial foi adicionada; fontes e pacote usam `.env.example`. Dados e logs de runtime ficam fora dos ZIPs. Interfaces novas renderizam texto escapado.

Não houve nova dependência. As versões locais principais de React, Vite, Vitest, TypeScript e Playwright foram comparadas ao lockfile e coincidem. Uma nova consulta online de CVEs não foi realizada; é pendência antes de publicação. Avisos de depreciação do TestClient/httpx/AnyIO e tamanho do bundle de mapa permanecem documentados; não impediram os testes.

## Estado e limites

- **Implementado e testado localmente:** entrada, fila, três níveis, cache, Score/evidências, projeção, budgets, controles, UI, migração e contratos de segurança descritos.
- **Homologado externamente:** nenhum provedor ou ambiente de produção neste ciclo.
- **Parcial por natureza:** a pesquisa usa as capacidades e limites das fontes atuais; ausência de confirmação de site permanece desconhecida. Descoberta pode terminar antes dos lotes progressivos; revisar a fila para o estado atualizado.
- **Pendente de ambiente externo:** PostgreSQL real, credenciais/quota/condições dos provedores, HTTPS/Docker/Railway, aparelhos físicos, Safari e leitor de tela. A compatibilidade SQL foi projetada, não homologada nesses ambientes.
- **Qualidade comercial real:** não medida; classificação e ordenação foram verificadas com dados controlados. Medir com casos e desfechos humanos da ORLIQ antes de afirmar aumento de conversão.
- **Bloqueio técnico local conhecido:** nenhum ao concluir os testes relatados. Sem autorização para deploy ou contato comercial.

## Pacotes e recibos

O empacotador valida base exata, arquivos preservados, conteúdo permitido, FULL extraído, dry-run sem gravação, recusa de customização, aplicação equivalente ao FULL, preservação de runtime sintético, recusa de reaplicação e rollback de fontes. Confirma os recibos internos e executa o verificador independente no FULL extraído. Os resultados finais e hashes dos ZIPs estão no recibo externo `release/PACKAGE-VALIDATION.json`.

Dentro do FULL, `release/PACKAGE-VALIDATION.json` e `release/SHA256SUMS.txt` verificam as fontes. Fora dele, os nomes iguais verificam os ZIPs finais. Essa diferença de escopo evita autorreferência e corrige a omissão da v1.38.2. Consulte [instalação](INSTALL-v1.38.3-dev.md).

## Capturas

- [Radar desktop](qa-v1.38.3-dev/investigation-desktop.png)
- [Preferências em 320 px](qa-v1.38.3-dev/investigation-settings-320.png)
- [Revisão no Radar em 390 px](qa-v1.38.3-dev/investigation-390.png)
