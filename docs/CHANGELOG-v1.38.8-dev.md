# Changelog — v1.38.8-dev

- Corrige a investigação automática desvinculada da pesquisa: SmartSearch usa um lote progressivo canônico rastreável pela rotina, com opt-in, orçamento e cancelamento existentes.
- Permite concluir a investigação já admitida ao atingir a meta de incorporações, sem admitir nova descoberta.
- Integra Operação do dia à Fila comercial do Radar: meta, origens, investigações, qualificação, motivos, pesquisas e operações recuperáveis.
- Ordena a atenção com índices existentes e desempate estável; preserva escolhas humanas e estados do CRM.
- Mantém seleção entre visões e operações e revalida versões para a próxima prévia. O detalhe reutiliza a seleção para investigar.
- Acrescenta testes de continuidade, isolamento, concorrência, orçamento, retomada, volume e jornada Chromium até preparação de rascunhos.
- Atualiza documentação corrente sobre a visibilidade pública observada; não altera a visibilidade do repositório.

Sem mudança de dependências, Score, definição da meta, provedor, scheduler ou migração (continua 033). Sem merge, deploy ou envio comercial.
