# ScoutLIQ v1.6.0 — Autonomous Territory Research

Base funcional: v1.5.1 (Web Research Agent + Deep Site Audit).

## Próximo nível

O Scout deixa de depender de abrir lead por lead para pesquisar. O Radar agora consegue colocar as melhores oportunidades visíveis em uma fila persistente e investigar uma por vez, com pesquisa web + auditoria profunda quando um site oficial é confirmado.

### Radar

- Nova ação **Investigar melhores**.
- Seleciona até 20 oportunidades visíveis na ordem atual do Radar.
- Ignora exemplos e, por padrão, não repete auditorias concluídas nos últimos 30 dias.
- Mostra progresso, concluídos, erros e quantos já estavam atualizados.
- Pode pausar, continuar e cancelar sem perder o estado da fila.
- Ao terminar cada estabelecimento, o lead atualizado volta para o Radar e o score pode se reposicionar imediatamente.

### Fila persistente

Nova camada persistente no backend:

- `research_batches`
- `research_batch_items`

A fila não depende de memória do processo. Se a página for recarregada, o Radar recupera a fila ativa. O processamento é deliberadamente sequencial para evitar rajadas de requests externas e manter o custo/controlabilidade previsíveis.

### Fluxo por estabelecimento

1. Pesquisa o site oficial e cruza evidências.
2. Atualiza site/contatos somente quando a identidade é suficientemente confirmada.
3. Se o modo for profundo e o site for confirmado, executa a auditoria multipágina da v1.5.
4. Persiste resultado individual e avança para o próximo lead.
5. Uma falha isolada não derruba a fila inteira.

### API

- `GET /api/research/batches/active`
- `GET /api/research/batches/{id}`
- `POST /api/research/batches`
- `POST /api/research/batches/{id}/step`
- `POST /api/research/batches/{id}/pause`
- `POST /api/research/batches/{id}/resume`
- `POST /api/research/batches/{id}/cancel`

### Migração

Nova revisão Alembic `009_research_batches.py`, dependente da revisão `008` de convergência da auditoria.

### Exportação

O export passa para `schema_version: 4` e inclui o histórico de filas de pesquisa.

### Validação

- 59 testes backend passaram com `TZ=America/Sao_Paulo`.
- 0 chaves duplicadas nos dicionários EN/ES.
- CSS: 0 erros de parsing.
- TS/TSX: validação sintática concluída.
- O build npm completo não foi concluído neste ambiente porque a instalação local de tipos ficou incompleta; o Railway continua sendo a validação final do bundle frontend.
