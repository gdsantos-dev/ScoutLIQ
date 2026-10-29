# Instalação de desenvolvimento — v1.38-dev em integração

Não é release homologada. Não aplicar em produção nesta etapa. A cópia integrada está em work/v1.38-dev/ScoutLIQ; a base work/v1.37.0/ScoutLIQ foi preservada.

Base exata do PATCH: FULL v1.37.0, SHA256 `4e7848fe58ade25bf96b87be0f16dbdb5f8086a9105c72dcf7e0367eb3b8b687`.

1. Use uma cópia de desenvolvimento da v1.37.0. Pare web/worker dessa cópia e faça backup consistente de banco e fontes. Não copie credenciais pessoais para pacotes.
2. Extraia o PATCH em outra pasta. Execute `python apply_release_patch.py --target CAMINHO_DA_COPIA` para conferir hashes. Conflitos devem ser integrados, nunca ignorados.
3. Aplique com `--apply` somente à cópia. O script guarda backup dos arquivos alterados; não executa migração nem modifica .env.
4. Instale `requirements.lock` no ambiente Python e execute `npm ci` e `npm run build` em frontend. Compile antes dos testes/importação do backend: o bootstrap estático herdado exige frontend/dist/assets.
5. Aponte DATABASE_URL exclusivamente ao banco de desenvolvimento e execute `python -m alembic upgrade head`. O head deve ser 028. Preserve as configurações de execução de worker existentes.
6. Valide Gerenciar → Negociações → Absorver pesquisa. Preview não cria Lead; confirmar cria somente os elegíveis no Radar, sem contato nem investigação automática.

A migração 028 adiciona duas tabelas, índices e FKs. Não altera tabelas anteriores. Instalação limpa e upgrade 027→028 são exercitados em SQLite descartável. Downgrade recusa apagar qualquer lote: reverta com backup consistente se for necessário voltar a uma instalação anterior após uso, preservando o histórico novo separadamente. Nunca exclua lotes diretamente para contornar a proteção.

Para reproduzir: `python -m pytest tests -q`; `npm test`; `npm run build`; `npm run typecheck:e2e`. Para navegador, após build: `python scripts/validate_browser_v138.py --group integration --port 8170`, escolhendo portas/bancos sintéticos ainda não usados. Chrome e dependências de desenvolvimento são necessários.

O FULL contém fontes/lockfiles/documentação, não banco, .env, dependências instaladas nem dist. Gere/verifique os artefatos desta etapa com `python scripts/package_integration_v138.py --base CAMINHO_DO_FULL_V137`. Os scripts históricos de release v1.37 permanecem disponíveis somente como histórico.
