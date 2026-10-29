# Instalação — v1.38.5-dev

Base exclusiva: FULL v1.38.4-dev, SHA256 `bdf663153db126da40474ac7001cd6a811ffdd95fbdc8d95dd64f0be77e1360e`.

1. Trabalhe em cópia de desenvolvimento. Pare web/worker e faça backup consistente do banco e fontes.
2. Extraia o PATCH em outra pasta. Execute `python apply_release_patch.py --target CAMINHO_DA_COPIA` para verificar hashes sem escrever.
3. Se a pasta `release/` da instalação contém recibos externos de distribuição, arquive-os fora dela e restaure ali os recibos internos do FULL v1.38.4 verificado. Os nomes coincidem, mas os escopos são diferentes. Não force hashes nem apague arquivos para contornar conflitos.
4. Com dry-run aprovado, execute novamente com `--apply`. O aplicador cria backup de fontes e preserva runtime; não migra banco automaticamente.
5. Instale `requirements.lock`; em `frontend`, execute `npm ci` e `npm run build`. O FULL contém fontes completas, sem dependências, dist, .env real ou banco pessoal.
6. Execute `python -m alembic upgrade head`: revisão **032 sobre 031**. Reinicie web e worker existentes. O acompanhamento não precisa de outro processo.
7. Abra Negociações → Acompanhamento comercial, confira o fuso do usuário, ajuste o intervalo e revise os efeitos antes de confirmar operações.

Downgrade 032 recusa apagar preferências, configurações ou operações de acompanhamento. Apenas cache sem decisão pode ser removido e reconstruído. Depois de uso humano, uma reversão exige preservar/reconciliar esses dados com backup consistente; não force downgrade. O rollback de fontes verificado no empacotamento não equivale a rollback destrutivo de banco.

## Verificação e reprodução

- FULL extraído: `python scripts/verify_followup_package.py --root CAMINHO/ScoutLIQ`.
- Backend: `python -m pytest -q`. `test_commercial_volume.py` cria seu diretório de saída automaticamente; a aplicação pode ser importada para testes sem dist.
- Frontend: `npm test`, `npm run build`, `npm run typecheck:e2e`.
- E2E novo: `python scripts/validate_browser_v1385.py --group followup --port 9000`.
- Fila v1.38.4: `python scripts/validate_browser_v1385.py --group commercial --port 9002`.
- Histórico completo: `python scripts/validate_browser_v1385.py --group complete --port 9020`.
- Use portas novas por execução; os bancos sintéticos são preservados como evidência e nunca substituem banco pessoal.
- Pacotes: `python scripts/package_followup_v1385.py --base CAMINHO_DO_FULL_V1384` após relatórios/capturas concluídos.

Recibos internos verificam o payload de fontes; os recibos externos junto aos ZIPs verificam os ZIPs finais. Essa separação evita autorreferência. Nenhum procedimento desta entrega autoriza deploy ou comunicação externa.
