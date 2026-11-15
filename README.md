# ScoutLIQ — código principal

**Repositório público:** [gdsantos-dev/ScoutLIQ](https://github.com/gdsantos-dev/ScoutLIQ). Versão importada: **v1.38.7-dev**, migração **033**. O código é público; dados operacionais, credenciais e ambientes de execução não fazem parte desta publicação.

Comece pelo [HANDOFF](HANDOFF.md) para execução, validação e limitações. Próximas alterações seguem [CONTRIBUTING](CONTRIBUTING.md), em branches e commits. As seções abaixo preservam o histórico das entregas; não substituem essas instruções de continuidade.

---

## v1.38.7-dev — Planejamento de prospecção

Plano diário em Automações, com autorização explícita, limites persistentes e execução pelo worker existente. Revisão **033 sobre 032**. Pacote de desenvolvimento; sem deploy ou homologação externa.

- [Instalação e PATCH](docs/INSTALL-v1.38.7-dev.md)
- [Arquitetura e contratos](docs/ARCHITECTURE-v1.38.7-dev.md)
- [Metas e indicadores](docs/METRICS-v1.38.7-dev.md)
- [Validação](docs/VALIDATION-v1.38.7-dev.md)
- [Changelog](docs/CHANGELOG-v1.38.7-dev.md)
- [Checkpoint](docs/CHECKPOINT-v1.38.7-dev.md)

# ScoutLIQ v1.38.6-dev

Inteligência operacional integrada: [contratos](docs/METRICS-v1.38.6-dev.md), [instalação](docs/INSTALL-v1.38.6-dev.md), [validação](docs/VALIDATION-v1.38.6-dev.md) e [checkpoint](docs/CHECKPOINT-v1.38.6-dev.md). Revisão 032 preservada; sem deploy ou envio comercial.

# ScoutLIQ v1.38.5-dev

Acompanhamento comercial supervisionado integrado ao Pipeline e Radar.

- [Fluxo e regras](docs/FOLLOWUP-v1.38.5-dev.md)
- [Instalação e migração 032](docs/INSTALL-v1.38.5-dev.md)
- [Validação](docs/VALIDATION-v1.38.5-dev.md)
- [Changelog](docs/CHANGELOG-v1.38.5-dev.md)
- [Checkpoint](docs/CHECKPOINT-v1.38.5-dev.md)

Empacotamento atual: `scripts/package_followup_v1385.py`. Documentação histórica abaixo permanece como referência.

# ScoutLIQ v1.38.4-dev — Operação Comercial em Lote

Base integrada v1.38.3-dev. Fila comercial no Radar, triagem humana com prévia e confirmação, até 50 empresas por operação e preparação de rascunhos canônicos sem envio. Migração aditiva 031 sobre 030.

- [Fluxo, regras, persistência e limites](docs/COMMERCIAL-OPERATIONS-v1.38.4-dev.md)
- [Validação e limites de homologação](docs/VALIDATION-v1.38.4-dev.md)
- [Instalação e recibos](docs/INSTALL-v1.38.4-dev.md)
- [Changelog](docs/CHANGELOG-v1.38.4-dev.md)
- [Arquivos alterados](docs/CHANGED-FILES-v1.38.4-dev.md)
- [Checkpoint](docs/CHECKPOINT-v1.38.4-dev.md)

Empacotador deste ciclo: `scripts/package_commercial_v1384.py`. As seções abaixo são históricas. Não houve deploy nem envio externo.

---

# ScoutLIQ v1.38.3-dev — Investigação Autônoma

Base integrada v1.38.2-dev. Investigação progressiva no worker compartilhado, entrada automática opcional, fila de até 100 empresas por solicitação, orçamento por usuário e revisão comercial com Score 3.0 preservado. Migração aditiva 030 sobre 029. Automação desligada por padrão; nenhum envio comercial.

- [Arquitetura, prioridade, fila e limites](docs/INVESTIGATION-v1.38.3-dev.md)
- [Validação e limitações](docs/VALIDATION-v1.38.3-dev.md)
- [Instalação, PATCH e recibos](docs/INSTALL-v1.38.3-dev.md)
- [Changelog](docs/CHANGELOG-v1.38.3-dev.md)
- [Checkpoint](docs/CHECKPOINT-v1.38.3-dev.md)


Use `scripts/package_investigation_v1383.py` para este ciclo. As seções, manifestos de overlay e scripts antigos abaixo são históricos. Não houve deploy, alteração de banco pessoal ou envio comercial.

---

# ScoutLIQ v1.38.1-dev — Busca Unificada com nicho opcional

Base: FULL integrado v1.38.0-dev, com Absorção e migração 028. Este ciclo permite explorar a localização selecionada sem preencher o pedido nem selecionar nichos. As fontes continuam limitadas à sua cobertura real, com qualificação pelo Score 3.0 existente.

- [Contrato, estratégia e changelog](docs/GENERAL-SEARCH-v1.38.1-dev.md)
- [Validação e limitações](docs/VALIDATION-v1.38.1-dev.md)
- [Instalação e PATCH incremental](docs/INSTALL-v1.38.1-dev.md)

Use `scripts/package_general_v1381.py` para empacotar este ciclo. Os documentos e scripts abaixo são históricos e não definem a base do PATCH atual. Não houve deploy, alteração de banco pessoal nem comunicação comercial.

---

# ScoutLIQ v1.38-dev em integração

Absorção JSON integrada à base exata v1.37.0 em 23/10/2026. Não é release homologada. A versão técnica do pacote é 1.38.0-dev.

- [Relatório de integração e validação](docs/INTEGRATION-v1.38-dev.md)
- [Contrato e operação da Absorção](docs/ABSORPTION-MVP-v1.38-dev.md)
- [Próximas alterações mapeadas](docs/NEXT-v1.38-dev.md)
- [Instalação em ambiente de desenvolvimento](docs/INSTALL-v1.38-dev.md)

A integração foi realizada em cópia isolada. A base v1.37.0, a instalação pessoal e seus bancos foram preservados. Não houve deploy nem contato comercial.

A documentação abaixo registra a base anterior. Para pacotes desta integração use scripts/package_integration_v138.py; os scripts de release v1.37 e seus manifestos/documentos históricos não certificam a v1.38-dev.

---

# ScoutLIQ 1.37.0 — Unified Search & Experience Refinement

Plataforma privada de prospecção comercial da ORLIQ. React/TypeScript/Vite, FastAPI, SQLAlchemy e Alembic. Identidade crimson/grafite, interface em pt-BR, en-US e es.

No Radar, **Buscar empresas** reúne pedido, localização e meta 25/50/75/100. Ajustes ficam recolhidos. Progresso, resultados e histórico permanecem no Radar; revisão comercial acontece na ficha. Mapa, consultas salvas e monitores usam o serviço compartilhado. Dados e motores comerciais existentes são preservados.

## Instalar ou atualizar

Siga [INSTALL-v1.37](docs/INSTALL-v1.37.md). O PATCH exige a base FULL v1.36.0 exata e recusa conflitos. Pare web/worker, faça backup, verifique/aplique o patch, instale requirements.lock, execute npm ci/build e migre para Alembic 027 antes de reiniciar. Nunca copie .env.example sobre suas credenciais. O worker precisa compartilhar o banco e o volume do web.

O FULL contém fontes e lockfiles; não inclui banco pessoal, credenciais, node_modules ou build pronto. O supervisor, rotinas e comunicação mantêm a operação documentada em [DEPLOY-v1.33](docs/DEPLOY-v1.33.md).

## Documentação atual

- [Changelog](docs/CHANGELOG-v1.37.md), [contrato de busca](docs/SEARCH-CONTRACT-v1.37.md), [geografia/custos](docs/LOCATION-CONTRACT-v1.37.md) e [compatibilidade](docs/SEARCH-COMPATIBILITY-v1.37.md).
- [Pesquisa visual](docs/DESIGN-RESEARCH-v1.37.md), [antes/depois](docs/BEFORE-AFTER-v1.37.md), [simplificação](docs/SIMPLIFICATION-v1.37.md), [CSS](docs/CSS-v1.37.md) e [idiomas](docs/LOCALES-v1.37.md).
- [Validação](docs/VALIDATION-v1.37.md), [segurança](docs/SECURITY-v1.37.md), [acessibilidade/performance](docs/ACCESSIBILITY-PERFORMANCE-v1.37.md), [limitações externas](docs/EXTERNAL-LIMITS-v1.37.md) e [checkpoint](docs/CHECKPOINT-v1.37.md).

Score 3.0, CommercialFit, evidências, CRM, aprendizado, Sites, Gmail OAuth, outbox e políticas de contato continuam existentes. Não há alteração automática de pesos. Documentos v1.20–v1.36 registram versões históricas; decisões e instruções atuais estão nos documentos v1.37.

## Validação reproduzível

Os testes abaixo usam ambientes locais e dados sintéticos; não executam prospecção real, envio comercial ou deploy. A entrega **v1.38.7-dev** registrou **592 testes backend, 27 testes unitários frontend e 77 testes E2E em 18 suítes**, conforme [evidências da versão](docs/VALIDATION-v1.38.7-dev.md) e [resumo de QA](docs/qa-v1.38.7-dev/validation.json). Esses números são resultados históricos da validação local; não constituem uma execução de CI ou garantia de que a suíte atual passou em outro ambiente.

**Pré-requisitos:** Python 3.12, Node.js 22, Google Chrome, dependências Python de desenvolvimento e dependências npm. Execute em um clone de desenvolvimento isolado, sem conectar bancos ou credenciais pessoais. No PowerShell, a partir da raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm ci
npm test
npm run build
npm run typecheck:e2e
cd ..
```

**Navegador E2E:** o runner atual é `scripts/validate_browser_v1387.py`, e não o runner histórico `v137`. Ele inicia servidores de fixtures sintéticas separados por suíte, usa o Chrome via Playwright e grava relatórios em `artifacts/`. A opção `complete` executa 14 suítes; as quatro suítes adicionais completam as 18 registradas na versão:

```powershell
.\.venv\Scripts\python.exe scripts/validate_browser_v1387.py --group complete --port 9180
.\.venv\Scripts\python.exe scripts/validate_browser_v1387.py --group operations --port 9220
.\.venv\Scripts\python.exe scripts/validate_browser_v1387.py --group commercial --port 9230
.\.venv\Scripts\python.exe scripts/validate_browser_v1387.py --group followup --port 9240
.\.venv\Scripts\python.exe scripts/validate_browser_v1387.py --group planning --port 9250
```

Use portas livres e **não reutilize** portas cujos bancos `data/e2e-<porta>.db` já existam: o runner recusa essa condição para proteger o isolamento. Se necessário, escolha novas faixas de portas. A presença de logs anteriores não substitui executar os testes novamente. Para detalhes de instalação e limites, consulte [HANDOFF](HANDOFF.md).

Homologação de PostgreSQL, provedores reais, Safari, dispositivos físicos e produção permanece separada da validação local. Nenhum envio comercial real ou deploy foi executado na entrega documentada.
