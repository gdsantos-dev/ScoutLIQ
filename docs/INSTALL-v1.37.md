# Instalação / atualização — ScoutLIQ v1.37.0

Base do PATCH: somente FULL v1.36.0 com hash 64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75. Nunca sobrescrever uma instalação em execução ou ignorar conflito de hash.

1. Pare web, supervisor e workers. Faça backup do banco e da configuração privada. Preserve volumes, identidade e arquivos de dados.
2. Para instalação nova, extraia o FULL em pasta nova. Para atualização, extraia o PATCH separadamente e execute `python apply_release_patch.py --target CAMINHO_DO_SCOUTLIQ`. Esse comando apenas verifica.
3. Se não houver conflitos, repita com `--apply`. O utilitário cria backup dos fontes alterados em .scoutliq-backups e preserva .env, banco e build local. Não aplica migrações automaticamente.
4. Instale `python -m pip install -r requirements.lock`. Em frontend, execute `npm ci` e `npm run build`. Não reutilize node_modules de outra versão.
5. Execute `python -m alembic upgrade head` (027) com os processos ainda parados. 027 cria location_cache/location_gate; mantém todas as tabelas de negócio e o ledger existente.
6. Revise .env.example sem copiar por cima do .env real. Limites novos: RADAR_LOCATION_DAILY_CALLS=300, RADAR_LOCATION_USER_DAILY_CALLS=100, RADAR_LOCATION_CACHE_SECONDS=3600. Podem ser reduzidos; zero bloqueia chamadas sem cache. Semântica continua desativada sem configuração/política explícita.
7. Reinicie pela operação já documentada em DEPLOY-v1.33.md. Web e worker precisam do mesmo banco/volume. Confira health/ready e worker heartbeat, login, uma busca e persistência após reinício.

Não publicar credenciais ou exemplos preenchidos. Tokens OAuth continuam protegidos pelos mecanismos existentes. A instalação de desenvolvimento e os testes não homologam produção.

## Reversão

Com processos parados, a migração 027 pode voltar a 026, removendo somente cache e gate, preservando o ledger de custo. Restaure os fontes da versão anterior e suas dependências ou o backup completo consistente. Não reduza além de 026: o ledger de comunicação tem sua própria proteção contra downgrade destrutivo. Antes de reverter, verifique compatibilidade das consultas criadas na v1.37; prefira restauração consistente de backup para voltar ao comportamento anterior. Testes de reversão de fontes ocorrem apenas em cópias descartáveis.
