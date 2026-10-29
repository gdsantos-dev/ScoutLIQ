# Instalação — ScoutLIQ 1.33.0 P0.1

FULL para pasta nova; PATCH exclusivo para FULL 1.32.0 de SHA256 `a4afe91edc0f626d732cfa2781e947a69f79991b3df0c0e180d0de72303104f7`. Esta entrega contém a primeira fatia operacional, não todas as frentes da v1.33. Fonte sem banco, .env real, credenciais, node_modules ou evidências de QA geradas.

## Nova instalação

Python 3.12+ e Node compatível com Vite 7. Na raiz extraída:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
npm run build --prefix frontend
```

Edite .env com origem, banco e credenciais próprias. Não use senhas sintéticas dos testes. Configure DEMO_SEED=false para operação; ambos os modos worker/combined precisam valer. Depois:

```powershell
python scripts/start.py
```

O comando migra até 022 e inicia web + worker. Não abra um segundo worker por engano. Verifique `/api/health/ready` e o estado em Automações. Para Docker/Railway, use [guia atual](DEPLOY-v1.33.md).

## PATCH

Pare web e worker. Faça backup consistente do banco (`scripts/backup.py`), .env e código da instalação. Extraia o PATCH fora dela:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

O preflight é somente leitura, compara hashes e recusa arquivos conflitantes. A aplicação cria backup das fontes afetadas. .env e banco não são incluídos nem substituídos. Não aplicar à 1.20, 1.29, 1.31 ou instalação divergente. Reinstale as dependências travadas, gere o build e execute `scripts/start.py`. Não aplique em produção sem janela/backup autorizado.

## Migração 022 e reversão

Adiciona seis campos a RadarSavedSearch e tabelas de execução, eventos, tentativas, operações e heartbeat. Pesquisas antigas começam disabled; não há ativação implícita. Não altera senha, sessão, identidade do lead, score/histórico, evidência, rascunho, política de contato, finanças ou CRM.

Downgrade 022 → 021 remove somente a estrutura de autonomia nova, usando DROP COLUMN nativo SQLite (3.35+). Perde agenda, autorizações de rotina e ledger. Não use downgrade para recuperar uma instalação integral: restaure backup consistente mais código correspondente. O teste de roundtrip usa banco sintético com registros canônicos comparados integralmente.

## Reproduzir QA

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q --basetemp=.runtime-tmp/pytest
npm test --prefix frontend
npm run typecheck:e2e --prefix frontend
python tests/process_acceptance.py
$env:E2E_PORT='8006'
python tests/smart_browser_fixture.py server
```

Em outro terminal com o mesmo E2E_PORT, configure E2E_ORIGIN=http://localhost:8006 e E2E_PYTHON para o Python instalado; execute `npm run test:e2e --prefix frontend`. O host usa `data/e2e-8006.db`, somente dados sintéticos; não exponha a porta. Os cenários criam workers controlados temporários. Os logs e capturas ficam em artifacts, fora dos pacotes.
