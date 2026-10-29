# Instalação — v1.38.6-dev

Base exclusiva: FULL v1.38.5-dev, SHA256 `7310028178df19e949295990cd81bba4037f5c04dd94f1602d463564fb8bfb22`.

1. Use uma cópia de desenvolvimento e faça backup consistente de fontes e banco. Pare web/worker antes de aplicar a atualização.
2. Extraia o PATCH fora da instalação. Execute `python apply_release_patch.py --target CAMINHO_DA_COPIA` para validar os hashes sem escrever.
3. Se `release/` contém recibos externos de distribuição, preserve-os fora da instalação e restaure nessa pasta os recibos internos do FULL v1.38.5-dev verificado. Os nomes coincidem, os escopos não. Não force hashes nem remova fontes para contornar conflito.
4. Após dry-run aprovado, execute novamente com `--apply`. O aplicador guarda backup de fontes e preserva runtime. Não migra bancos automaticamente.
5. Instale `requirements.lock`; em `frontend`, use `npm ci` e `npm run build`. O FULL é de fontes completas, sem dependências, dist, credenciais ou dados pessoais.
6. A revisão continua **032**. Não há migração 033 nem alteração de esquema neste ciclo. O comando habitual `python -m alembic upgrade head` continua válido para uma instalação compatível.
7. Reinicie os processos existentes. Abra a área Inteligência/Histórico e selecione Funil, Eficiência ou Qualidade comercial. Os filtros não alteram dados.

Reversão de fontes não exige downgrade do banco neste ciclo. Não execute downgrade 032: ele pertence ao acompanhamento já existente e protege dados humanos. Não realize deploy ou envios comerciais como parte desta instalação de desenvolvimento.

## Reprodução

- FULL extraído: `python scripts/verify_operations_package.py --root CAMINHO/ScoutLIQ`.
- Backend: `python -m pytest -q` (banco sintético temporário).
- Frontend: `npm test`, `npm run build`, `npm run typecheck:e2e`.
- Novo E2E: `python scripts/validate_browser_v1386.py --group operations --port 9200`.
- Regressão: grupos `complete`, `commercial` e `followup`, sempre em novas portas e sem reutilizar banco da fixture.
- Volume: `python -m pytest tests/test_operational_intelligence.py -k volume -q`.
- Empacotamento: `python scripts/package_operations_v1386.py --base CAMINHO_DO_FULL_V1385` após validação/documentação/capturas concluídas.

Recibos internos verificam fontes e seu manifesto. Recibos externos verificam os ZIPs finais, evitando autorreferência. Consulte METRICS-v1.38.6-dev.md e VALIDATION-v1.38.6-dev.md antes de interpretar números como evidência comercial.
