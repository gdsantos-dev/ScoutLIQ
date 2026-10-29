# Checkpoint — v1.38.5-dev

Base integrada: `work/v1.38.4-dev/ScoutLIQ`, FULL hash registrado em INSTALL. Implementação: `work/v1.38.5-dev/ScoutLIQ`. Não reiniciar a partir de versões antigas.

Arquivos centrais:

- `backend/followup.py`: planejador, projeções locais, preferências, elegibilidade, chave de rascunho e efeitos supervisionados.
- `backend/followup_models.py` e migração `032_commercial_followup.py`: preferências e índice, sem mensagens/tarefas concorrentes.
- `backend/commercial_review.py`: reutilização da prévia/confirmacão da v1.38.4 e lista operacional paginada.
- `backend/main.py`/`schemas.py`: atividades manuais declaradas e export.
- `backend/communication_replies.py`: guarda contra substituir próxima ação preenchida.
- `frontend/src/components/CommercialQueue.tsx`, `Pipeline.tsx` e integração em `App.tsx`: mesma lista/editor nos pontos existentes.
- `tests/test_followup.py`, `test_followup_migration.py`, `frontend/e2e/followup.spec.ts`: cenários novos.
- `scripts/package_followup_v1385.py` e `verify_followup_package.py`: FULL/PATCH, hashes, conflitos, preservação e reversão de fontes em cópias descartáveis.

Leia `VALIDATION-v1.38.5-dev.md` e `release/PACKAGE-VALIDATION.json` para resultados efetivos. A existência deste checkpoint não comprova conclusão de testes ou pacotes.

Próximo ciclo: homologar PostgreSQL/ambiente-alvo e navegação em dispositivos físicos quando autorizado; revisar dependências antes de publicação e avaliar sugestões com casos reais ORLIQ. Manter preparação, revisão de conteúdo, condição de contato, autorização e envio separados. Nenhum ciclo futuro deve inferir autorização de deploy ou contato a partir desta entrega.
