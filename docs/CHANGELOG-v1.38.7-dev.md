# v1.38.7-dev — Planejamento Autônomo de Prospecção

- Plano diário em Automações, desativado por padrão, com prévia e autorização explícita.
- Metas, locais, pesquisas, prioridade, dias, janela, cooldown e limites validados no backend.
- Coordenação pelo mesmo `schedule_due` e RoutineRun, sem outro worker ou descoberta paralela.
- Fencing e idempotência; pausa/desativação preservam dados e interrompem jobs vinculados.
- Progresso por empresas canônicas novas, origem do crédito e exclusão de descartes comprovados.
- Sugestões com evidência da Inteligência Operacional, sem alteração automática de critérios.
- Histórico, estados operacionais e atualização de progresso na interface existente.
- Migração 033 sobre 032, aditiva, com recusa de downgrade destrutivo quando há planos.
- Teste histórico da revisão 032 passa a solicitar explicitamente essa revisão, preservando seu contrato após a nova head 033.

Sem deploy, contatos comerciais, dependências adicionais ou remake visual. Homologação de provedores e PostgreSQL permanece externa.
