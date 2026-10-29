# Instalação — ScoutLIQ 1.35.0

FULL é código completo para pasta nova; PATCH é exclusivo para o FULL 1.34.0 de SHA256 `46f5b86e0ab08441a73843648a0a3e49d6027b1c930b64186ab1a6c623e34582`. Não inclui banco, `.env`, tokens, dependências instaladas ou build. Nenhuma instalação pessoal foi modificada nesta entrega.

## Pasta nova

Python 3.12+, SQLite 3.35+ e Node compatível com Vite 7. Na pasta extraída:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
npm run build --prefix frontend
python scripts/start.py
```

Editar o `.env` privado antes de iniciar: origem, banco, credenciais próprias e DEMO_SEED=false em operação. O supervisor existente migra até 026 e inicia web/worker compartilhando banco/volume. Saúde em `/api/health/ready`. Requisitos de Docker/Railway e volume: DEPLOY-v1.33.md. Semântica opcional: INTELLIGENCE-v1.34.md. Gmail: GMAIL-v1.35.md; continua desligado até configuração explícita. Aprendizado supervisionado não exige modelo pago.

## PATCH e backup

Parar web e worker. Fazer backup consistente do banco, código e ambiente. Extraia PATCH fora da instalação:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

Primeiro comando só verifica hashes; segundo aplica e guarda backup dos arquivos. Fonte local divergente provoca recusa sem escrita. Preserva banco, `.env` e cache local; não faz migração de dados em produção durante a aplicação de fontes. Reinstalar requirements.lock (inclui cryptography), executar npm ci/build e iniciar supervisor. Não aplicar sobre v1.33 ou instalação customizada sem resolver a divergência.

## Migrações / reversão

- **024:** casos revisados, versões, prévias e avaliações congeladas.
- **025:** configurações/propostas/histórico de calibração e `leads.score_criteria_json={}`. Critério padrão permanece equivalente à v1.34; só muda por aprovação explícita.
- **026:** contas de canal, states OAuth, verificações de contato, outbox, eventos e mensagens recebidas. Nenhum Lead/CRM duplicado.

Downgrade elimina dados novos; preferir restauração consistente de backup com código correspondente. A 025 recusa critério ativo não padrão; reverter a calibração explicitamente antes de considerar downgrade. A 026 recusa apagar ledger com pendências ou qualquer tentativa de rede, inclusive aceitas/incertas. **Não apagar ledger para liberar reenvio.** Depois de envios, uma restauração de banco antigo pode perder recibos e permitir duplicação: manter envio desativado até reconciliar o provedor e o histórico. Rollback técnico não desfaz envio externo. Exportar os dados antes de qualquer manutenção.

## Reproduzir QA

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q --basetemp=.runtime-tmp/pytest
npm test --prefix frontend
npm run typecheck:e2e --prefix frontend
python scripts/evaluate_commercial_quality.py
python scripts/verify_score_baseline.py --base C:\caminho\ScoutLIQ-v1.34.0-full-source.zip
python tests/process_acceptance.py
```

E2E legado/aprendizado: iniciar `tests/intelligence_browser_fixture.py` com E2E_PORT=8015, usar E2E_ORIGIN=http://localhost:8015 e E2E_PYTHON absoluto no Playwright. Executar os seis arquivos herdados + learning em grupos que respeitem o rate limit de login. Reiniciar somente o servidor sintético entre grupos, sem reduzir a proteção da aplicação. E2E de comunicação: `tests/communication_browser_fixture.py`, porta 8016; executar somente communication.spec.ts com origem/porta/Python correspondentes. O worker chamado pelo teste usa exclusivamente Gmail controlado.

Fixtures devem ouvir somente loopback, usando bancos `data/e2e-<porta>.db`. Não expor esses hosts, não usar `.env` de produção nem contas reais. Não gerar outro build enquanto o host está aberto. As chaves e identidades nos arquivos de teste são sintéticas e não podem ser reutilizadas na operação.
