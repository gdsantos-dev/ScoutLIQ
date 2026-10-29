# Instalação de desenvolvimento — v1.38.1-dev

O PATCH exige o FULL integrado v1.38.0-dev: ScoutLIQ-v1.38-dev-integration-FULL.zip, SHA256 f66a5097486760825f3f3ba1b33c5cab7036a81bd1ce282010b414afe916232b. Não aplicar sobre v1.37 nem sobre a instalação histórica.

1. Em uma cópia de desenvolvimento, pare web/worker e faça backup consistente de fontes e banco. Preserve .env e dados fora dos pacotes.
2. Extraia o PATCH em outra pasta. Rode `python apply_release_patch.py --target CAMINHO_DA_COPIA` para conferir os hashes sem gravar. Ajustes locais conflitantes exigem integração manual; não force a aplicação.
3. Aplique com `--apply`. O aplicador cria backup dos arquivos alterados; não roda migrações nem sobrescreve dados/credenciais. Reaplicação é recusada.
4. Instale requirements.lock no ambiente Python. Em frontend, execute `npm ci` e `npm run build`. O FULL contém fontes, não dependências nem dist; o bootstrap do backend exige build prévio.
5. Não há migração nova. O head continua 028. Uma instalação limpa deve executar `python -m alembic upgrade head` contra seu banco de desenvolvimento. Web e worker compartilham o mesmo banco/volume e a configuração existente.
6. Valide Buscar empresas com pedido vazio, localização selecionada, meta 50. Confirme cobertura da fonte. Texto desconhecido exige revisão. Absorção conserva seu fluxo anterior.

Para voltar da v1.38.1-dev à base integrada, pare os processos e restaure os arquivos pelo backup do aplicador, removendo apenas os novos arquivos enumerados no manifesto. Não faça downgrade da 028: ela já integra a base. Antes de operar sobre dados pessoais, faça backup consistente e valide a cópia restaurada.

Validação local: `python -m pytest tests -q`; em frontend `npm test`, `npm run build`, `npm run typecheck:e2e`. Navegador: `python scripts/validate_browser_v1381.py --group general --port 8230` usando portas e bancos sintéticos ainda não utilizados. Chrome e requirements-dev são necessários. Para uma única suíte, acrescente `--suite general-search`. Não aponte fixtures para bancos pessoais.

Empacotamento: `python scripts/package_general_v1381.py --base CAMINHO_DO_FULL_INTEGRADO`. O script verifica a base, fontes protegidas, migrações, hashes do FULL, equivalência PATCH/FULL, dry-run, conflito, dados sintéticos preservados, reaplicação recusada e rollback de fontes em instalações descartáveis. Não realiza deploy nem migra banco.
