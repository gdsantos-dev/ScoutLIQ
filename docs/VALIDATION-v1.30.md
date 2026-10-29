# Validação — ScoutLIQ 1.30.0

Execução local em Windows em 09/10/2026, com SQLite e dados sintéticos. Base: ScoutLIQ-v1.29.0-ecosystem-integrations-full.zip, SHA256 `f38b0f3576ef0748e3f5998e499b2fe8c481cdeec0b87a028b85680a9026f182`. A extração original ficou separada da candidata; a instalação histórica v1.20 não foi substituída.

## Resultados executados

| Validação | Resultado | Evidência local em artifacts/ |
| --- | --- | --- |
| Backend original 1.29 | 107 testes passaram | baseline-python-verified.txt na extração original |
| Backend candidato completo | 124 passaram; 2 avisos de depreciação | pytest-final.txt |
| Fluxo novo e migração após ajuste final do snapshot de aprovação | 17 passaram | workflow-pytest-final.txt |
| Frontend unitário | 22 passaram | vitest-final.txt |
| Typecheck E2E | Passou | e2e-typecheck.txt |
| Build de produção após correções finais da interface | Passou; aviso de chunk MapLibre maior que 500 kB | build-final.txt |
| Navegador: fluxo operacional | 3 passaram | workflow-e2e-final.txt |
| npm audit | 0 vulnerabilidades reportadas | npm-audit-final.json |
| pip-audit do requirements.lock | Nenhuma vulnerabilidade conhecida reportada | pip-audit.json |

As contagens se sobrepõem: os 17 testes direcionados fazem parte dos 124 do backend, não são testes adicionais. As auditorias de dependências refletem o catálogo consultado nesta execução, não garantia permanente de ausência de vulnerabilidades.

O cenário principal de navegador cria evidência, confirma sua classificação, prepara e aprova abordagem, recarrega e verifica persistência, altera o conteúdo e verifica revogação. Verifica também que o CRM não registra envio fictício. Inclui axe no painel do novo fluxo. Os outros cenários cobrem vazio, erro 503, recuperação, teclado/Escape, movimento reduzido e ausência de overflow horizontal em 320, 390, 768 e 1440 px. Capturas desktop e mobile foram inspecionadas visualmente. Isso não equivale a auditoria de acessibilidade de todo o produto nem teste em aparelhos físicos.

Os testes de backend cobrem isolamento entre usuários/objetos, campos extras rejeitados, evidência vencida/revisada, aprovação vinculada ao conteúdo, referência de autorização, idempotência da preparação, bloqueio de contato, pausa após resposta, exportação e ausência de transmissão no dispatch. A migração 018 → 019 → 018 → 019 foi executada em banco descartável, com preservação dos registros anteriores.

## Regressão histórica: avaliação limitada e pendências

A execução histórica foi limitada a três falhas: **5 passaram, 3 falharam e 17 não foram executados**. Não há alegação de suíte E2E completa aprovada.

1. `v1.26 action queue: management opens on execution surface`: contraste apontado pelo axe em Ações. Reproduzido no servidor da base original após inclusão das mesmas quatro empresas sintéticas usadas na comparação; sem esses dados, o cenário original passou. As cores observadas variam com as transições, portanto a equivalência é do cenário e da classe de falha, não de cada valor de cor.
2. `v1.25 visual polish: quiet shell, fields and responsive navigation`: seletor `.page-head` não encontrado, também reproduzido na base original.
3. `mobile remaining modules: opportunities, monitors, campaigns, automations, settings and about`: documento com largura 392 px em viewport de 390 px em outro módulo; também reproduzido na base original.

Logs: candidata `artifacts/legacy-e2e.txt`; original `artifacts/baseline-ui-confirmed.txt` e `artifacts/baseline-ui-same-data.txt`. A comparação válida confirmou pelo OpenAPI que o servidor original não possuía as rotas novas. Uma tentativa anterior com conflito de porta foi descartada como evidência.

Foram corrigidos o overflow de Negociações em 320 px e o cabeçalho que extrapolava em 768 px, confirmados pelo novo cenário responsivo. A suíte histórica limitada foi executada antes dos ajustes finais de navegação e rodapé da ficha; os três novos cenários foram reexecutados depois. Os 17 cenários históricos restantes e a correção dos três problemas herdados seguem pendentes.

## Desempenho observado

Uma amostra de 12 leituras locais de `/workflow`, com uma evidência e um rascunho, mediu p50 aproximado de **32,5 ms** e p95 de **51,9 ms**. Não é teste de carga, de rede pública ou de provedor. Não mede FPS. O build mantém o aviso de tamanho do MapLibre; otimização de chunks segue pendente. Não foram homologados PostgreSQL, Docker/Railway, HTTPS público, Safari ou dispositivos físicos.

## Empacotamento reproduzível

`scripts/build_release.py --base <ZIP-original>` gera FULL fonte e PATCH por hashes. `scripts/verify_release.py --base <ZIP-original>` verifica o manifesto, igualdade PATCH → FULL, preflight sem escrita, backup dos arquivos alterados, preservação de runtime e recusa de reaplicação/conflito local. O resultado efetivamente executado fica em `artifacts/release-validation.json`, e os hashes dos ZIPs ficam em `release/SHA256SUMS.txt`.

Os ZIPs excluem .env real, banco, node_modules, dist, logs, capturas e dados de teste. As evidências locais podem conter dados sintéticos de autenticação nos traces de navegador e não devem ser publicadas indiscriminadamente. Os motores originais de scoring, pesquisa, providers, automação e enrichment foram comparados por hash e preservados.

## Estado da entrega

- **Implementado e testado:** evidências persistidas, classificação humana, ficha Operação, preparação idempotente, edição, aprovação vinculada ao conteúdo, histórico, bloqueio por oportunidade, pausa após resposta manual, exportação e migração.
- **Parcial:** primeira fatia operacional termina na aprovação e no registro auditável; não executa envio oficial. Modelos PT/EN/ES preservam o idioma original das evidências.
- **Não iniciado nesta fatia:** adapters Gmail/WhatsApp, OAuth, webhooks de respostas, worker/filas de execução, follow-ups automáticos, aprovação em lote e redesign integral. Não se trata apenas de credenciais faltantes. O dispatch retorna 503 sem simular sucesso.
- **Pendente de homologação:** produção, provedores reais, retenção e regras por mercado, aparelhos físicos e suíte histórica integral. Nenhuma mensagem comercial real foi enviada e nenhum deploy foi realizado.

Veja AUDIT-v1.30.md para prioridades e SECURITY-GATE-v1.30.md para revisão explícita de segurança e seus limites.
