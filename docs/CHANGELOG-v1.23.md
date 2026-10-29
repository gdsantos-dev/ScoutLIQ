# ScoutLIQ 1.23.0 — Gestão Mobile

## Objetivo
Terceiro ciclo pós-redesign da v1.20.0. A v1.22.0 permanece como baseline funcional e este release recompõe as quatro superfícies de Gestão para celular sem alterar backend, banco, migrations ou regras comerciais.

## Negociações
- O pipeline mobile passa a funcionar como lista operacional contínua, sem herdar a leitura de colunas do desktop.
- Resumo de negociações, potencial em aberto e ações para hoje ganham hierarquia compacta própria para tela estreita.
- Etapas do pipeline usam trilho horizontal para touch.
- Cada negociação concentra empresa, próxima ação, valor e mudança de etapa numa sequência vertical clara.
- O drag continua disponível no desktop; no celular, a mudança de etapa permanece acessível pelo seletor.

## Clientes
- A tabela desktop permanece intacta e é substituída no celular por uma lista mobile dedicada.
- Cada cliente exibe identidade, situação do projeto, serviço, valor vendido e recebido sem depender de colunas ocultas.
- Recebimentos pendentes ficam acessíveis diretamente na linha mobile.
- Contexto comercial e detalhes do cliente continuam ligados aos fluxos existentes, sem duplicar regra de negócio.

## Sites / Entregas
- A tabela desktop permanece intacta e o celular recebe workspace próprio em lista.
- Cada site apresenta cliente, status, domínio, renovação, margem mensal e alertas em leitura progressiva.
- Resumo financeiro dos sites ativos é recomposto em matriz 2×2 para mobile.
- Abrir site e detalhes continuam disponíveis sem transformar a tela em tabela horizontal comprimida.

## Financeiro
- O ledger mobile deixa de usar tabela responsiva e passa a renderizar linhas próprias para A receber, Vendas, Recebimentos e Custos.
- Resultado de caixa, recebimentos, custos e métricas secundárias ganham hierarquia específica para celular.
- As abas de movimentações passam a rolar horizontalmente em touch.
- Ações de receber e excluir permanecem ligadas aos mesmos handlers e confirmações existentes.

## Limites deste ciclo
- Desktop preservado estruturalmente.
- Nenhuma migration.
- Nenhuma alteração de schema, endpoint, Score Engine, automações, regras de venda ou regras financeiras.
- Campanhas, Monitores, Oportunidades, Automações, Configurações, About, formulários e estados vazios globais continuam reservados para a v1.24.0.
- Polish geral de desktop + mobile continua reservado para a v1.25.0.
