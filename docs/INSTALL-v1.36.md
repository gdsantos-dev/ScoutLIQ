# Instalação — ScoutLIQ 1.36.0

FULL contém todas as fontes, incluindo migrações até 026. PATCH aplica somente sobre o FULL v1.35.0 exato, SHA256 `2e5bac34cbe21dd40224991fa874a58655b5863847b1ac0efcdc3e8cf51981f6`. Não inclui banco, `.env`, tokens, node_modules nem build. A instalação pessoal não foi modificada.

## Instalação nova

Requisitos mantidos da v1.35: Python 3.12+, SQLite 3.35+ e Node compatível com Vite 7.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
npm run build --prefix frontend
python scripts/start.py
```

Configurar o `.env` privado antes de iniciar: origem, banco, contas próprias e DEMO_SEED=false. O supervisor existente inicia web/worker compartilhando banco/volume. Saúde: `/api/health/ready`. Configuração de produção: `DEPLOY-v1.33.md`; semântica opcional: `INTELLIGENCE-v1.34.md`; Gmail: `GMAIL-v1.35.md`. Esta entrega não publica nada e não habilita envios.

## PATCH

Parar web e worker e fazer backup consistente de código, banco e ambiente. Extrair PATCH fora da instalação:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

O primeiro comando confere hashes sem escrever; o segundo guarda backup das fontes e aplica. Divergências locais são recusadas sem escrita. Banco, `.env` e cache ficam preservados. Executar `npm ci --prefix frontend` e `npm run build --prefix frontend`, depois reiniciar o supervisor. Não aplicar sobre outras versões ou personalizações sem resolver a divergência.

## Migrações e rollback

**Nenhuma migração nova. Head continua 026.** As 74 fontes de backend/migrações permanecem idênticas ao FULL v1.35. Um rollback desta camada de UX pode restaurar as fontes v1.35 e refazer o build; não executar downgrade do banco para reverter aparência. Manter o ledger de comunicação. Backup antigo de banco pode perder recibos de envio: nunca restaurar banco para desfazer apenas uma mudança visual. Limitações de migrações anteriores: `INSTALL-v1.35.md`.

## Reproduzir validação

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q --basetemp=artifacts/pytest-local
npm test --prefix frontend
npm run typecheck:e2e --prefix frontend
python scripts/verify_score_baseline.py --base C:\caminho\ScoutLIQ-v1.35.0-full-source.zip
```

Build concluído antes de iniciar os E2E; não regenerar chunks durante testes. Hosts sempre em loopback, bancos sintéticos próprios e E2E_ORIGIN/E2E_PORT/E2E_PYTHON correspondentes:

| Grupo | Host / fixture | Arquivos Playwright |
|---|---|---|
| Workspace | `scripts/start_e2e.py --preview --port 8016` | redesign, experience |
| Busca/ficha | `tests/smart_browser_fixture.py server`, E2E_PORT=8020 | smart-search, workflow |
| Inteligência | `tests/intelligence_browser_fixture.py`, E2E_PORT=8021 | autonomy, intelligence, learning |
| Comunicação | `tests/communication_browser_fixture.py`, E2E_PORT=8023 | communication |

Usar `npx playwright test ... --output=../artifacts/test-results-GRUPO --reporter=list` dentro de frontend. Grupos paralelos precisam de bancos e diretórios de relatório separados. Comunicação exige fixture limpa: o limite real de intervalo entre tentativas pode reagendar uma segunda mensagem após uma execução anterior. Não reduzir essa proteção para tornar um teste verde. Nunca conectar essas fixtures a contas ou dados reais.
