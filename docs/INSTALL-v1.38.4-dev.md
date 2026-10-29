# Instalação — v1.38.4-dev

Base exclusiva: FULL v1.38.3-dev, SHA256 `accfa6c0baf4ec928928d2cea5d68e8f92ec46b2bb41bc8fc5807c754fa40421`.

1. Use uma cópia de desenvolvimento. Pare web/worker e faça backup consistente de banco e fontes.
2. Extraia o PATCH em outra pasta. Execute `python apply_release_patch.py --target CAMINHO_DA_COPIA`. O dry-run verifica hashes antes de alterar qualquer arquivo.
3. Se a cópia usa a pasta `release/` para recibos externos de distribuição, arquive esses recibos fora dela e restaure os **recibos internos** do FULL v1.38.3 verificado nos mesmos caminhos antes do dry-run. Os nomes são iguais, mas o escopo é diferente. Não apague recibos nem force hashes para contornar conflitos.
4. Após dry-run aprovado, repita com `--apply`. O aplicador preserva runtime e cria backup dos arquivos alterados; não migra o banco.
5. Instale `requirements.lock`; em `frontend`, execute `npm ci` e `npm run build`. O FULL contém fontes completas, não dependências ou dist.
6. Execute `python -m alembic upgrade head` na cópia: revisão **031 sobre 030**. Reinicie web e worker existentes. A fila comercial não precisa de outro worker.
7. Abra Radar → Fila comercial. A indexação inicial é local; pode exigir mais de um bloco em instalações grandes. Revise e confirme as ações antes de executá-las.

A 031 adiciona duas tabelas e índices. Não altera registros anteriores. Downgrade recusa apagar decisões ou operações persistidas. Um índice sem decisões pode ser descartado e reconstruído. Após uso comercial, reversão exige backup consistente e reconciliação dos dados novos; não force downgrade.

## Recibos

O FULL inclui `release/PACKAGE-VALIDATION.json`, `release/SHA256SUMS.txt` e `RELEASE-MANIFEST.json` para verificar suas fontes. Após extrair, execute:

`python scripts/verify_commercial_package.py --root CAMINHO_DO_FULL_EXTRAIDO/ScoutLIQ`

Ao lado dos ZIPs, os recibos externos com os mesmos nomes contêm os hashes dos arquivos ZIP finais. Compare com `Get-FileHash -Algorithm SHA256 CAMINHO_DO_ZIP`. A separação de escopo evita autorreferência.

## Reprodução

- Backend: `python -m pytest -q`, usando ambiente de teste isolado.
- Frontend: `npm test`, `npm run build`, `npm run typecheck:e2e`.
- E2E novo: `python scripts/validate_browser_v1384.py --group commercial --port 8800`.
- E2E histórico: `python scripts/validate_browser_v1384.py --group complete --port 8820`.
- Use portas novas: cada execução possui banco sintético próprio, preservado como evidência.
- Pacotes: `python scripts/package_commercial_v1384.py --base CAMINHO_DO_FULL_V1383`, após gerar relatórios e capturas.

Nenhum procedimento desta entrega autoriza deploy ou contato externo.
