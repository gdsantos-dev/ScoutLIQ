# Metas e indicadores do planejamento

| Indicador | Definição e evidência |
|---|---|
| Meta diária | Volume configurado de empresas novas; não é promessa de resultado nem meta de oportunidades qualificadas. |
| Empresas novas | `COUNT(Lead)` do proprietário, `demo=false`, `created_at` dentro do dia local; exclui observações explícitas de descarte na incorporação. O ID canônico impede múltipla contagem por origem. |
| Descartados fora da meta | Cadastros novos cujo SmartSearch registrou grupo `discarded` na incorporação; continuam no Radar, fora do crédito da meta. Candidatos descartados antes da incorporação nunca entram no COUNT. |
| Incorporadas pelo plano | Mesma população, com PlanIncorporation → PlanDecision → plano explicitamente vinculado ao run criador. Reencontro de empresa existente não cria esse crédito. |
| Outras incorporações | Total menos crédito explícito do plano. Inclui Absorção e cadastro manual; não é medida de oportunidades qualificadas. |
| Pesquisas encerradas | Runs vinculados ao plano e iniciados no dia que saíram de running/paused, inclusive parciais, cancelados e skipped. |
| Pesquisas com meta própria concluída | Somente RoutineRun `completed`; a meta própria da SmartSearch é distinta da meta de novas empresas do plano. |
| Pesquisas em execução | Runs iniciados no dia com estado running/paused. |
| Decisões de adiamento | Eventos de motivo/estado distintos no dia. Não equivale a uma contagem de tentativas de rede nem de pesquisas perdidas. |
| Investigações iniciadas pelo plano | WorkAttempt kind=batch, ID de item distinto, ligado ao run do plano, com início no dia local. Retentativas do mesmo item não são novas empresas investigadas. |
| Investigações pendentes | Estoque atual da conta em lotes/itens canônicos pending/running/paused. Não é um histórico reconstruído da fila. |
| Operações | ProviderOperation por data de reserva local, unido ao WorkAttempt do run. Inclui reserved, failed e completed; sem preço inferido. |
| Próxima avaliação | Data indicativa condicionada à janela, cooldown, limites, executor e fonte. Não é horário garantido de execução. |

A fronteira diária é meia-noite local da conta, não um bloco fixo de 86.400 segundos. Limites globais do worker mantêm o dia UTC. Jobs não atravessam a janela autorizada.

O histórico é recalculado a partir de registros canônicos atuais; exclusões de Leads e jobs podem reduzir contagens anteriores. Não se inventam snapshots removidos. Metas efetivamente registradas nas decisões são mostradas para dias anteriores; se houve mudança, aparecem os valores registrados, sem aplicar silenciosamente a meta atual ao passado. O fuso apresentado é o configurado no plano; decisões guardam seu fuso original para auditoria.

Descarte anterior à revisão 033 sem observação persistida não é reconstruído de forma especulativa. A cobertura histórica de descartes é parcial. A contagem bruta `incorporated` da Inteligência Operacional 1.38.6 permanece preservada e pode ser maior que o crédito de meta do plano, que exclui descartes explícitos. Nenhum dos dois números significa qualificação comercial.

Dados de contagem não alteram Score, critérios de seleção nem prioridades humanas. As sugestões reutilizam diagnósticos canônicos de 7 dias e informam sua população. O agendador não recalcula esse relatório. Ausência de evidência produz ausência de sugestão, sem inferir superioridade de região, setor ou fonte.

Consulta de histórico: até 366 dias, com até 200 decisões exibidas por dia e indicação de truncamento. Opções de pesquisas: até 200 por nome, com aviso; participantes por plano: até 20. Não há estimativa de custo monetário.
