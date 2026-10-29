# Instalação de desenvolvimento — v1.38.2-dev

Base obrigatória: `ScoutLIQ-v1.38.1-dev-FULL.zip`, SHA256 `2a92b87a7eb4c0d513698df05fc18dca7ac5e3d373d41a6a0d0b42bcb7879229`. O PATCH não é para versões anteriores ou para a instalação pessoal histórica.

1. Prepare uma cópia de desenvolvimento, pare web/worker e faça backup consistente de fontes e banco. Preserve `.env` e dados separadamente.
2. Extraia o PATCH em outra pasta. Rode `python apply_release_patch.py --target CAMINHO_DA_COPIA`. O dry-run verifica hashes sem gravar. Não force conflitos de customizações locais.
3. Aplique com `--apply`. O aplicador faz backup dos arquivos alterados; não sobrescreve `.env`, bancos ou arquivos de runtime, nem executa migrações. Reaplicação é recusada.
4. Instale `requirements.lock` no ambiente Python; em `frontend`, rode `npm ci` e `npm run build`. FULL contém fontes; dependências e dist não acompanham o pacote. O bootstrap backend precisa do build prévio.
5. Execute `python -m alembic upgrade head` no banco da cópia: head 029, aditiva sobre 028. Reinicie web e worker existentes com o mesmo banco/volume. Não crie outro executor.
6. Abra CRM > Absorver pesquisa. Cole JSON ou selecione CSV/TSV/JSON UTF-8. Confira mapeamento, analise e confirme os elegíveis. Use “Completar pendências” para enfileirar os incompletos. Consultas externas são opcionais e dependem da fonte Geoapify já configurada. Sem credenciais, use cache e correção manual.
7. Confira uma confirmação parcial seguida de correção/segunda confirmação, pausa/cancelamento e retomada de histórico. Não trate sugestões como investigação comercial ou autorização para contato.

Validação: `python -m pytest -q`; frontend `npm test`, `npm run build`, `npm run typecheck:e2e`. E2E completo: `python scripts/validate_browser_v1382.py --group complete --port 8500` (portas e bancos de fixture novos). Chrome, requirements-dev e dependências npm são necessários. Fixtures nunca devem apontar para dados pessoais. Uma suíte pode ser selecionada com `--suite absorption-intelligent`.

Empacotamento: `python scripts/package_absorption_v1382.py --base CAMINHO_DO_FULL_V1381`. Confere base/hashes/motores preservados e testa dry-run, conflito, equivalência FULL/PATCH, preservação de runtime sintético, reaplicação e rollback de fontes em cópias descartáveis.

Rollback: pare os processos e preserve todos os dados novos. Antes do uso da 029, uma cópia sem novos originais/correções/jobs pode executar `alembic downgrade 028`; a migração recusa perda de histórico. Depois do uso, restaure backup consistente de banco e código em outra cópia, reconciliando os dados novos; não force downgrade. O backup de arquivos do aplicador não substitui backup do banco. A migração 028 e sua Absorção já pertencem à base e não devem ser removidas.

Nenhuma homologação real de provedor, PostgreSQL, Docker, Railway ou produção está incluída nesta validação local.
