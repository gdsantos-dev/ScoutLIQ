# ScoutLIQ: instruções para continuidade

- Fonte principal: repositório privado `gdsantos-dev/ScoutLIQ`, branch `main`. Ler HANDOFF.md e CONTRIBUTING.md antes de continuar.
- Atualizar a referência remota, criar branch `codex/<assunto>`, fazer commits descritivos e usar pull request para integrar próximas alterações. Não sobrescrever histórico remoto.
- A base desta publicação é o FULL v1.38.7-dev, migração 033. Não reconstruir mecanismos já concluídos. Preservar estrutura, dados, autenticação, autorização, Score 3.0, rotinas e worker.
- Não versionar `.env`, secrets, tokens, bancos, dados pessoais, backups ou logs de runtime. `.env.example` deve conter somente exemplos sem segredos.
- Validar entradas e permissões por objeto no backend; manter limites, idempotência, segurança e isolamento entre usuários. Nunca resolver problemas desabilitando controles.
- Preservar identidade ORLIQ/ScoutLIQ, tokens crimson/grafite, copy funcional e acessibilidade/mobile; evitar interfaces redundantes e redesign fora do escopo.
- Distinguir implementado, testado localmente, parcial e não homologado. Não atribuir a fixtures resultados comerciais reais.
- Push não autoriza deploy, migração de banco pessoal, consumo de cotas externas ou envio comercial. Essas ações exigem autorização própria.
- ZIPs e cópias em `work/` são históricos; não substituem o histórico Git para desenvolvimento futuro.
