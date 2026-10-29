# Instalação — v1.38.3-dev

PATCH exclusivo para o FULL v1.38.2-dev de SHA256 `39fb92f3f4bf87c35cfea5a244001107e923bdaa568e3fa4e96d3726c35e0cd2`. Use uma cópia de desenvolvimento, com backup consistente de banco e fontes. Não aplicar a versões anteriores.

1. Pare web e worker da cópia. Preserve `.env`, uploads e bancos separadamente.
2. Extraia o PATCH em outra pasta e rode `python apply_release_patch.py --target CAMINHO_DA_COPIA`. O dry-run verifica todos os hashes sem alterar o destino.
3. Havendo sucesso, repita com `--apply`. Customizações e conflitos são recusados; não force sobrescrita. O aplicador guarda os arquivos anteriores e não migra o banco. Se a instalação guarda recibos externos antigos em `release/`, arquive-os fora da cópia antes do dry-run; os dois recibos internos novos pertencem ao código entregue. O aplicador recusa substituição silenciosa desses arquivos.
4. Instale `requirements.lock`; em `frontend`, execute `npm ci` e `npm run build`. Os pacotes são FULL de fontes, sem dependências, dist, segredos ou runtime.
5. Na cópia, execute `python -m alembic upgrade head`: revisão 030 sobre 029. Reinicie web e worker existentes, compartilhando banco e volume. Não criar outro executor.
6. Em Configurações, escolha Busca, Absorção ou ambas, limites e profundidade; salve. A automação começa desligada. No Radar, selecione empresas ou use “Investigar melhores”. Abra a fila para acompanhar, pausar, cancelar e revisar resultados.

Após uso da 030, o downgrade é recusado se houver preferências persistidas ou histórico progressivo. Para reverter, preserve dados novos e restaure backup consistente de banco e código em outra cópia, reconciliando as alterações. Backup de arquivos do PATCH não substitui backup do banco.

## Recibos verificáveis

O FULL contém `ScoutLIQ/release/PACKAGE-VALIDATION.json` e `ScoutLIQ/release/SHA256SUMS.txt`. O recibo interno identifica a base e o escopo da validação. O SHA interno verifica os arquivos de fontes, excluindo os próprios recibos e o manifesto para evitar autorreferência. `RELEASE-MANIFEST.json` inclui também os recibos internos.

Ao lado dos ZIPs, `release/PACKAGE-VALIDATION.json` e `release/SHA256SUMS.txt` verificam os **arquivos ZIP finais**. São recibos de distribuição externos, com escopo diferente e explicitado; o hash de um ZIP não pode ficar dentro dele próprio.

Após extração, rode `python scripts/verify_investigation_package.py --root CAMINHO_DO_FULL_EXTRAIDO/ScoutLIQ`. O comando confere manifesto, recibos e hashes das fontes. Para os ZIPs, compare `Get-FileHash -Algorithm SHA256 CAMINHO_DO_ZIP` com o recibo externo.

## Reprodução local

- Backend: `python -m pytest -q` em ambiente de teste isolado.
- Frontend: `npm test`, `npm run build`, `npm run typecheck:e2e`.
- Browser: `python scripts/validate_browser_v1383.py --group complete --port 8600` e `--group investigation --port 8620`, usando portas/fixtures novas e Chrome instalado.
- Empacotamento: `python scripts/package_investigation_v1383.py --base CAMINHO_DO_FULL_V1382` após gerar as capturas de QA.

Os testes usam provedores controlados. Nenhum procedimento desta entrega autoriza envio comercial ou deploy.
