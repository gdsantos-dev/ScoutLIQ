# Planejamento autônomo de prospecção — v1.38.7-dev

Base exclusiva: FULL v1.38.6-dev, revisão 032, SHA256 `dbf392f49ae3c13e699b7b345743f164774953717747f39c06b136e1e1a04f79`. A revisão 033 é aditiva. Não houve deploy nem acesso ao banco de produção.

## Contratos conferidos

| Contrato existente | Integração |
|---|---|
| Busca Geral / Unificada, RadarSavedSearch e SmartSearch | Mantêm intenções, território e fonte. A busca geral continua sem setores e sem nichos inseridos pelo plano. |
| `routines.schedule_due`, RoutineRun e RoutineEvent | Um único caminho `schedule_saved` cria os mesmos jobs e eventos canônicos. Recorrências e planos disputam admissão pela data devida; só uma admissão por tick. |
| WorkAttempt, ProviderOperation e `consumption.reserve` | Mesma reserva persistente antes da chamada. Uma guarda adicional aplica consentimento, janela e orçamento do plano. Reservas e falhas contam como operações. |
| `research_worker` | Preservado. Usa o mesmo lease, token, executor e recuperação de jobs. O planejamento não depende de aba ou processo web aberto. |
| Investigação Autônoma, pesquisa e evidências | Preservadas. SmartSearch já cria ResearchBatch, evita investigações ativas em outro lote e aplica cooldown de pesquisa recente. |
| Inteligência Operacional | Preservada. As sugestões consultam o relatório canônico de 7 dias somente por ação do usuário; o scheduler usa agregações específicas. |
| Score, Comercial Learning e selection_quality | Preservados. Não há reponderação, novo score, extrapolação comercial ou aplicação automática de sugestão. |
| CRM, Radar, histórico e comunicação | Cadastros, decisões comerciais, drafts, políticas e motores de comunicação preservados. Nenhum envio é autorizado pelo planejamento. |

## Consentimento e limites

Um plano por conta, inicialmente desativado. Até 20 pesquisas participantes, com prioridade explícita 1–5 e locais provenientes das próprias pesquisas. O backend recusa IDs de outra conta, locais divergentes, campos extras e valores fora dos limites.

A prévia informa dias, janela, fuso, meta, fontes, cobertura declarada, limites do plano, limites originais das rotinas e limites globais. A ativação/retomada exige confirmação booleana explícita e o hash da prévia atual. Mudanças de critérios, fonte, configurações globais ou fuso invalidam a autorização. A prévia não testa credenciais pela rede e não comprova disponibilidade externa.

Cada pesquisa coordenada roda no máximo uma vez por dia local. O cooldown efetivo é o maior entre o intervalo original e o intervalo do plano, ambos com mínimo de 24 h. A política é deliberadamente conservadora: uma fonte com baixo rendimento, falha ou cobertura esgotada não é repetida no mesmo dia para perseguir a meta. A configuração original não é aumentada nem reescrita. Pesquisas desativadas continuam desativadas.

O plano controla no máximo uma rotina por conta ao mesmo tempo e aguarda buscas abertas. O limite de empresas é também aplicado ao retorno de um adaptador que entregue mais resultados que o solicitado. O número bruto examinado pela fonte continua sendo evidência técnica, sem ser reduzido artificialmente.

O efetivo é o menor limite aplicável: plano, rotina, executor e provedor. Continuam valendo tarefas diárias, concorrência, leases, prazo, páginas, candidatos e investigações. A janela é no mesmo dia local; janelas noturnas que cruzam meia-noite são recusadas explicitamente. Intervalos locais usam ZoneInfo, inclusive mudança de horário de verão. Os limites globais continuam por dia UTC.

Pausar ou desativar encerra os jobs vinculados e invalida seus tokens; resultados já persistidos ficam preservados. Pausar mantém as pesquisas participantes sob controle do plano. Editar um plano pausado mantém essa pausa e exige nova autorização. Desativar devolve as pesquisas ativas às recorrências originais previamente autorizadas, sem apagar dados. A interface informa essa diferença.

## Concorrência e recuperação

O planejamento usa a transação curta do executor existente, com UPDATE condicional e fencing. SQLite serializa as escritas; PostgreSQL usa o lock da mesma linha. Nenhum lock é mantido durante uma chamada de rede. As operações da API reutilizam esse fence somente para alterações de configuração/estado, evitando corrida com a admissão. Não foi introduzido outro lock global permanente.

`RoutineRun(saved_search_id, scheduled_at)` continua único. Cada decisão agendada aponta para um único run, e `plan_id + key` torna decisões idempotentes. A restrição de uma incorporação por Lead impede crédito duplicado. Dois workers não criam dois jobs para a mesma admissão. Uma tentativa expirada pode repetir uma leitura, mas seu token antigo não pode persistir efeitos.

Planos são selecionados por próxima avaliação e ID estável, competindo com a próxima data da rotina avulsa. Planos que aguardam cooldown, janela ou orçamento não monopolizam a fila; a consulta trata no máximo um plano e 20 membros por tick. Dentro de um plano, prioridade explícita, última execução e ID definem uma ordem determinística. Com pouco histórico, essa distribuição é neutra, sem ranking inventado de lucratividade.

O worker global continua sendo um único executor por banco, inclusive no PostgreSQL. A compatibilidade SQL foi projetada para ambos; testes locais são SQLite. Não se declara homologação PostgreSQL, horizontalização do worker ou SLA de produção.

## Persistência e auditoria

`prospecting_plans` guarda proprietário, configuração, versão, estado, fuso, autorização e próxima avaliação. `prospecting_plan_members` relaciona pesquisas existentes. `prospecting_plan_decisions` registra versões, motivos, configurações e referências a RoutineRun. `prospecting_plan_incorporations` guarda apenas referências ao Lead/SmartSearch/decisão e a observação de descarte na incorporação, sem copiar dados da empresa.

Uma busca fora do plano pode registrar a observação de descarte para a contagem diária, mas tem `decision_id` nulo e jamais ganha crédito pelo plano. Não há preenchimento retroativo nem atribuição de jobs antigos.

A exclusão de pesquisa com execução/tentativa vinculada ao plano no dia local é recusada até outro dia. Isso evita que o CASCADE histórico remova joins usados pelo orçamento e permita executar novamente além do limite. Pausa e desativação continuam disponíveis imediatamente; pesquisas não executadas pelo plano podem ser excluídas normalmente. O teste cobre a recusa no mesmo dia e a liberação no dia seguinte.

Revisão 033 cria quatro tabelas e um índice de `(user_id, created_at)` em Leads. Não altera tabelas históricas além do índice. Upgrade é aditivo e reexecutável via Alembic. O downgrade recusa remover planos existentes: recuperação de uma instalação com dados exige backup compatível, não exclusão de histórico humano.

## Indicadores e limitações

Veja `METRICS-v1.38.7-dev.md`. Sugestões expõem observação, período, população e contagem; filas são estoque atual, não eventos comerciais. Amostras pequenas permanecem identificadas. Nada estima faturamento, lucro, custo monetário, conversão ou tempo humano economizado.

Leituras operacionais não chamam provedores. Não há IA paga, novo scheduler, motor comercial paralelo, novo painel independente, campanha, alteração de política de destinatários ou envio comercial.
