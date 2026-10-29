# ScoutLIQ 1.26.0 — Execução Comercial

A v1.26.0 abre um novo ciclo de produto depois do roadmap de reconstrução mobile e polish encerrado na v1.25.0. O objetivo é transformar dados que já existem no Pipeline em uma superfície diária de execução, sem criar um segundo sistema de tarefas e sem alterar banco, migrations ou regras de negócio do backend.

## Nova área Ações

`Gerir clientes` passa a abrir em **Ações**. A fila reúne oportunidades ativas em três recortes:

- **Hoje**: próximas ações com vencimento no dia, ações explícitas sem data e primeiros contatos que já precisam de atenção;
- **Atrasadas**: próximas ações vencidas, oportunidades antigas ainda sem primeiro contato e negociações sem contato recente;
- **Próximas**: próximas ações explícitas com data futura.

A fila é derivada de `next_action`, `next_action_on`, `stage`, `last_contact_at`, `pipeline_added_at`, `created_at` e Opportunity Score. Nenhuma tabela nova foi criada.

## Prioridade explicável

A ordenação considera três grupos de sinais já disponíveis:

1. urgência de prazo;
2. estágio comercial;
3. Opportunity Score.

O valor interno usado para ordenar não é apresentado como uma nota de prioridade. Cada linha mostra os fatores concretos que explicam sua posição, como vencimento, etapa e Score atual.

## Execução rápida

Cada item pode aproveitar os contatos existentes da empresa para:

- abrir WhatsApp;
- iniciar ligação;
- abrir e-mail quando o enriquecimento possui endereço disponível;
- registrar WhatsApp, ligação, e-mail, reunião, proposta ou resposta no histórico comercial;
- remarcar a próxima ação;
- concluir uma próxima ação explícita;
- abrir o Context Panel completo da empresa.

Registrar uma interação usa o endpoint de atividades já existente. Remarcar e concluir usam o endpoint de próxima ação já existente.

## Pipeline parado sem tarefa explícita

A fila também detecta dois casos sem gravar estado adicional:

- oportunidade sem primeiro contato após o período inicial no Pipeline;
- oportunidade já contatada que ficou vários dias sem nova interação.

Ao registrar um contato, `last_contact_at` já é atualizado pelo backend existente e o item derivado deixa de aparecer automaticamente quando deixa de cumprir o critério.

## Navegação e mobile

- **Ações** é a primeira opção do ambiente Gerir clientes;
- uma troca inicial de Operar → Gerir clientes abre a fila;
- se o usuário já estava em outra página de gestão, a navegação continua lembrando a última página durante a sessão;
- desktop e mobile usam a mesma lógica e a composição da fila se reorganiza para touch em viewport estreito.

## Compatibilidade

- backend: sem alterações;
- migrations: sem alterações;
- banco: sem alterações;
- endpoints: sem endpoints novos;
- dados existentes: reutilizados diretamente;
- v1.25.0 permanece a baseline do patch incremental.
