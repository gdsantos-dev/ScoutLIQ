# Validação local — P0.1 da v1.33.0

Data: 16/10/2026. Base exclusiva FULL 1.32, conferida por hash e manifesto. Código trabalhado em pasta nova; nenhum banco pessoal, .env real ou credencial de provedor foi utilizado nos testes. Nenhuma produção alterada.

## Backend e preservação

- Regressão completa: **178 testes passaram**, 91,42 s, em `artifacts/pytest-release.txt`.
- Após dois ajustes finais (contadores de investigação em interrupção por orçamento e bloqueio de troca de fonte dentro de uma concessão), **37 testes de rotina/SmartSearch passaram**, 29,73 s, em `artifacts/pytest-budget-final.txt`. Incluem dois casos novos: são **180 cenários backend distintos aprovados em rodadas complementares**, não uma alegação de suíte única com 180.
- Migração 022 → 021 → 022 comparou integralmente usuários, sessões, leads, atividades, evidências, rascunhos, políticas de destinatário e buscas, além dos campos anteriores de pesquisas salvas. `integrity_check` e `foreign_key_check` passaram. Os registros sintéticos incluem evidência revisada e conteúdo aprovado; nenhuma aprovação habilita envio.
- Casos novos: agenda sem disparo implícito, um job por slot, repetição no mesmo segundo, duplicação semântica da rotina, supressão de empresa já apresentada, cooldown, recusa preservada, limites de tarefa/operação/adapter, reserva concorrente antes da chamada, custo monetário desconhecido, prazo/pausa/cancelamento, exclusão, fonte alterada, DTO extra, versão antiga, CSRF e propriedade entre contas.

## Processos reais locais

`tests/process_acceptance.py` iniciou Uvicorn e worker reais sobre SQLite descartável. Readiness confirmou ambos; matar o worker encerrou web e retornou exit 1. Novo início ficou saudável e parada graciosa encerrou os filhos com exit 0. Evidência: `artifacts/process-acceptance.json` e log. O teste de lease recuperado usa relógio/expiração controlados e confirma que o token antigo não grava, o novo confirma uma única identidade e o ledger preserva ambas as tentativas. Não é teste de desligamento físico da máquina ou do Railway.

## Frontend e navegador

**35 cenários distintos de navegador aprovados em rodadas complementares.** A rodada geral (`artifacts/e2e-release.txt`) teve 34 aprovados e a medição intermediária de contraste descrita abaixo. A rodada final (`artifacts/e2e-verified-final.txt`) aprovou os três cenários executados: o contraste da fila de Ações e os dois fluxos novos. A cobertura legada inclui autenticação, idiomas, CRM, Sites, finanças, campanhas, regras, pesquisas, ficha operacional, offline/erros e layouts de 320 a 1920 px. Não se declara uma execução única 35/35.

Build de produção e TypeScript de aplicação/E2E passaram; **23 testes unitários passaram**. Nova configuração validada em 320, 390, 768 e 1440 px, sem overflow horizontal; auditoria axe das regras WCAG selecionadas sem violações no formulário, Escape e movimento reduzido. Capturas de configuração, mobile e resultado conferidas visualmente. Histórico exibe antes/depois com rótulos legíveis, sem exigir leitura de JSON.

O cenário de autonomia salvou/ativou/agendou pela interface, fechou a página e iniciou o loop contínuo do worker em processo separado. A rotina terminou e a página reaberta apresentou duas empresas qualificadas e uma descartada. Limites e contadores persistiram; fontes/investigações eram adapters sintéticos, portanto zero operações de rede nesse cenário é esperado. Reservas de operações reais de adapter foram verificadas separadamente por testes controlados, sem conexão comercial externa.

## Pacotes verificados

FULL: **256 arquivos de fonte, mais manifesto**. PATCH exato 1.32 → 1.33: **47 entradas verificadas**. Aplicado em cópia descartável, o PATCH reproduziu todos os hashes do FULL, preservou .env/banco/cache sintéticos e criou backups compatíveis. Preflight não escreveu; reaplicação e conflito local foram recusados sem alterar a cópia. **44 arquivos de backend/migrações permaneceram idênticos à base**, incluindo verificações explícitas dos motores de score, regras, evidências e outreach. Evidência: `artifacts/release-validation.json`; checksums dos arquivos distribuídos: `release/SHA256SUMS.txt`.

Os pacotes não contêm runtime. Varredura dos 256 arquivos de fonte não encontrou padrões de chaves privadas ou tokens comuns; isso complementa a inspeção de variáveis/segredos, sem prometer detecção universal. O verificador reproduz a aplicação segura em `scripts/verify_release.py`.

## Dependências e limites da homologação

`npm audit` retornou zero vulnerabilidades conhecidas; `pip-audit -r requirements.lock --no-deps --disable-pip` também não encontrou alertas na consulta desta execução. Logs ficam em artifacts. Permanecem avisos conhecidos de bundle do mapa acima de 500 kB e duas depreciações da infraestrutura Python de testes; não foram tratados como falhas da aplicação.

Não homologados externamente: Docker/Linux com abandono de UID, Railway/volume/restart, HTTPS/domínio/cookies de produção, PostgreSQL, fornecedores reais/cobertura/cotas/preços, operação 24/7, Gmail, WhatsApp, conversão comercial, dispositivos físicos e leitor de tela. A primeira fatia implementa P0.1; P0.2/P0.3/P0.4 e WhatsApp continuam conforme o changelog.

## Reprodução e evidências

Comandos em [INSTALL-v1.33.md](INSTALL-v1.33.md). Logs, imagens, traces, bancos sintéticos e cópias descartáveis estão em artifacts/data/.runtime-tmp, excluídos dos ZIPs de código. A suite não foi enfraquecida para esconder falhas. Uma rodada foi interrompida porque um rebuild durante E2E invalidou assets em cache; o host foi reiniciado com build estável. Uma medição de contraste capturou opacidade intermediária da transição JS: o helper agora espera página carregada e opacidade 1, além de aguardar animações finitas, antes de manter o mesmo requisito axe.

A repetição isolada da autonomia encontrou três qualificadas porque outro cenário havia revisado manualmente a independência da terceira empresa sintética. O setup agora remove somente as três empresas dessa fonte controlada antes da execução, assim como já fazia o teste de SmartSearch. A expectativa de duas qualificadas/uma descartada foi mantida e passou; nenhum dado pessoal foi envolvido.
