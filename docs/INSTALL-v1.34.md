# Instalação — ScoutLIQ 1.34.0 / P0.2

FULL para pasta nova. PATCH exclusivo para o FULL 1.33.0 de SHA256 `f4915a73ffc2231e092ae9397c23c7bcd42f44213fb5567ca1d97c4be3d6b03e`. Nenhum banco pessoal, `.env` real, chave, dependência instalada ou build está incluído.

## FULL

Python 3.12+ e Node compatível com Vite 7. Na raiz extraída:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
npm run build --prefix frontend
python scripts/start.py
```

Antes de iniciar, edite origem, banco e suas credenciais em `.env`; DEMO_SEED=false para operação. Mantenha combined/worker de P0.1. O supervisor aplica até 023 e inicia ambos os processos. Prontidão em `/api/health/ready`. Requisitos Docker/Railway/volume continuam em [DEPLOY-v1.33.md](DEPLOY-v1.33.md). A semântica fica desabilitada até configuração explícita descrita em [INTELLIGENCE-v1.34.md](INTELLIGENCE-v1.34.md).

## PATCH e reversão

Pare web/worker, faça backup consistente de banco, `.env` e código. Extraia o PATCH fora da instalação:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

O primeiro comando confere hashes sem escrever. Arquivo modificado localmente causa recusa integral. O segundo cria backup das fontes afetadas; preserva banco e `.env`. Não aplique sobre instalação antiga ou divergente. Reinstale dependências travadas, gere build e inicie pelo supervisor. Não houve aplicação em produção nesta entrega.

A migração 023 adiciona apenas semantic_gate e semantic_attempts. Não altera estruturas de P0.1, identidade, MFA/sessões, leads, evidências, rascunhos, contatos, Sites ou finanças. Roundtrip 023 → 022 → 023 compara todas as tabelas da v1.33 em banco sintético.

Downgrade elimina o ledger semântico: desabilite o modelo e preserve o histórico/backup antes de usá-lo. Para restauração íntegra, prefira backup consistente + código correspondente. Não reinicie cobranças incertas por apagamento de ledger. Os campos aditivos de plano/contexto em JSON são ignorados pela v1.33, mas cursores adaptativos de jobs novos não devem ser retomados pelo código antigo: cancele essas buscas antes de reverter, ou restaure o backup anterior completo.

## Reproduzir validação

```powershell
python -m pip install -r requirements-dev.txt
npm run build --prefix frontend
python -m pytest -q --basetemp=.runtime-tmp/pytest
npm test --prefix frontend
npm run typecheck:e2e --prefix frontend
python scripts/evaluate_commercial_quality.py
python tests/process_acceptance.py
$env:E2E_PORT='8010'
python tests/intelligence_browser_fixture.py
```

Em outro terminal, configure o mesmo E2E_PORT, E2E_ORIGIN=http://localhost:8010 e E2E_PYTHON com caminho absoluto do Python; execute `npm run test:e2e --prefix frontend`. O host só ouve loopback e usa `data/e2e-8010.db`; não exponha o servidor de teste. Apenas a resposta externa de modelo e os provedores de pesquisa são controlados. Aplicação, HTTP, banco, autenticação, worker e UI são reais locais. Não gere outro build enquanto o host estiver aberto.
