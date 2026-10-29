# Validação local — ScoutLIQ 1.34.0 / P0.2

17/10/2026. Base exclusiva FULL v1.33.0, SHA256 `f4915a73ffc2231e092ae9397c23c7bcd42f44213fb5567ca1d97c4be3d6b03e`; 256 arquivos conferidos pelo manifesto antes da extração. Instalação pessoal, banco e credenciais reais não foram usados. Sem deploy ou envio comercial.

## Resultados

| Verificação | Resultado local | Evidência gerada |
|---|---|---|
| Regressão completa backend | 204 aprovados, 58,91 s | artifacts/pytest-release.txt |
| Rechecagem específica após rótulo de procedência | 23 aprovados | artifacts/pytest-final.txt |
| Frontend unitário | 23 aprovados em 7 arquivos, também no build final | artifacts/frontend-tests-final.txt |
| TypeScript app/E2E e build produção | Aprovados | artifacts/build-final.txt, e2e-types-final.txt |
| Navegador | 37 cenários distintos aprovados em rodadas complementares | artifacts/e2e-release.txt, e2e-final.txt |
| Migração 023 → 022 → 023 | Todas as tabelas da v1.33 preservadas; integrity_check/FKs válidos | tests/test_opportunity_migration.py na regressão completa |
| Supervisor real local | Worker caiu → web encerrou/exit 1; reinício e parada normal/exit 0 | artifacts/process-acceptance.json |
| Dependências | npm audit completo e produção: 0 vulnerabilidades conhecidas; pip-audit lock: nenhuma conhecida | artifacts/npm-audit-all.json, npm-audit.json, pip-audit.json |

Os 37 cenários de navegador não representam uma rodada única 37/37. A rodada geral executou 36 cenários: 34 aprovados e duas falhas de helper/seletor descritas abaixo. A rodada complementar aprovou os dois cenários corrigidos e um cenário adicional de contatos, totalizando 37 distintos. A última conferência visual dos dois fluxos P0.2 está em `artifacts/e2e-polish.txt` e nas capturas `intelligence-mobile.png`, `intelligence-desktop.png` e `intelligence-contacts.png`.

## O que foi efetivamente exercitado

- Semântica desativada/configuração incompleta; schema e ausência de tools/store; sucesso controlado; campos extras, setor/exclusões inválidos, alteração de meta/cidade, país inferido, recusa, resposta incompleta, uso excedente e timeout. Chamada repetida não cobra novamente. Duas reservas concorrentes respeitam o orçamento restante; uma reserva incerta continua consumindo após reabertura do banco. Erro externo não vaza texto sensível.
- Autenticação/CSRF; propriedade entre contas nas rotas herdadas; cancelamento/lease obsoleto; recuperação, orçamento e repetição da rotina de P0.1. Remover uma conta não reembolsa consumo semântico global.
- Plano cobre setores suportados, mantém offsets independentes, prioriza rendimento técnico observado, não chama setor sem capacidade e encerra repetição. Continua dentro de SmartSearch/ResearchBatch/ResearchExecutor. Resultado persiste depois de fechar o navegador e executar worker separado.
- Contatos com host exato, rejeição de e-mail múltiplo e caminhos sociais incompatíveis, números conflitantes sem escolha arbitrária, manutenção do valor do operador, escopo por URL, ausência de inferência negativa em HTML truncado e evidências prováveis no modelo existente.
- Fluxo HTTP real local de pesquisa → evidência/contexto → ficha → reload. Resposta externa é controlada; banco, APIs, autorização, UI e persistência são reais locais.
- Nova interpretação em 320, 390, 768 e 1440 px, sem overflow horizontal; axe nas regras WCAG selecionadas, teclado/Escape e movimento reduzido. A regressão herdada cobre demais módulos e larguras até 1920 px. Inspeção visual corrigiu nomes internos de critérios na ficha.

## Falhas intermediárias resolvidas

O seletor novo usava getByLabel exato, mas a árvore acessível expunha corretamente o combobox Interpretação; a consulta passou a usar role/name observados. O helper herdado de acessibilidade esperava page-view mesmo fora da área autenticada; agora aguarda esse contêiner somente no produto e main nas telas de autenticação. A auditoria axe permaneceu integral, sem suprimir regras. Ambos passaram na rechecagem.

A primeira tentativa de backend ocorreu antes de existir dist/assets e falhou no carregamento do host. Após build, os testes rodaram. Um caso novo iniciou com modo legacy por falta da configuração de fixture; foi corrigido para worker e aprovado na regressão completa. Esses erros não foram descartados como sucesso.

## Preservação e pacote

Score Engine, automações, rotinas, consumo de operações, modelos de P0.1, supervisor/start, motor de outreach e migração 022 permaneceram byte a byte iguais à base. `research_worker.py` recebeu somente a persistência do novo contexto após auditoria, sob o fence existente. Nenhum segundo scheduler, executor ou score foi criado.

Os scripts build_release/verify_release conferem manifestos e hashes, ausência de runtime nos ZIPs, preflight sem escrita, aplicação que reproduz o FULL, preservação de `.env`/banco/cache sintéticos, backups, recusa de reaplicação e de conflito local. Resultado mecânico e hashes finais ficam em `artifacts/release-validation.json` e `release/SHA256SUMS.txt`; scripts e instruções de reprodução estão incluídos no FULL.

Verificação mecânica aprovada: 271 arquivos de fonte no FULL, 40 entradas de PATCH e 48 arquivos de backend/migrações idênticos à base. Preflight não escreveu; PATCH reproduziu o FULL; dados/configuração/cache sintéticos e backups foram preservados; reaplicação e conflito local foram recusados sem alteração. A busca por padrões comuns de chaves privadas/tokens no ZIP não encontrou ocorrências; não substitui revisão de conteúdo.

## Qualidade comercial e limites

Sete fixtures sintéticos herdados: TP=1, FP=0, FN=0, TN=6; prioridade e seleção idênticas ao baseline Score 3.0. Precisão e recall sintéticos=1, NDCG@10=1, precisão nos sete itens=1/7. Não há resultado de vendas ou rótulo humano real; nenhuma melhoria comercial real foi demonstrada. Avaliação reproduzível em `scripts/evaluate_commercial_quality.py`.

Sem homologação externa de modelo/provedores, custos faturados, Gmail/OAuth, WhatsApp, Railway/Docker/HTTPS, dispositivos físicos ou leitores de tela. O aviso herdado de chunk de mapa acima de 500 kB e duas depreciações Python permanecem; não são falhas dos testes. P0.3/P0.4 continuam pendentes, com requisitos técnicos e ponto de retomada em [CHECKPOINT-v1.34.md](CHECKPOINT-v1.34.md). Esta entrega não declara a missão completa.
