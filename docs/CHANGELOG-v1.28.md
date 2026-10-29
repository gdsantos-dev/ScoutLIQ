# ScoutLIQ 1.28.0 — Inteligência do histórico comercial

A v1.28.0 transforma o histórico comercial já existente em leitura operacional explicável. A nova área **Histórico** compara negociações ganhas e perdidas sem criar probabilidade de fechamento ou um score paralelo.

## O que entrou

- nova página `Histórico` em **Gerir clientes**, disponível em desktop e mobile;
- resumo de negociações encerradas, taxa histórica observada e cobertura dos dados;
- comparação de medianas entre ganhos e perdas para:
  - tempo até o primeiro contato;
  - duração do ciclo até o desfecho;
  - número de interações;
  - número de follow-ups;
- padrões comportamentais descritivos para proposta, reunião, resposta, follow-up e primeiro contato em até um dia;
- cada padrão mostra taxa nos ganhos, taxa nas perdas, diferença em pontos percentuais e tamanho da amostra;
- leitura da etapa imediatamente anterior às perdas a partir do histórico de mudanças de estágio;
- reaproveitamento dos snapshots de ganhos × perdas já existentes para mostrar contexto das oportunidades no momento do desfecho;
- estado de amostra insuficiente explícito antes de comparar padrões;
- navegação mobile de Gestão com labels compactos para acomodar a nova área sem esmagar os itens existentes;
- lógica de análise isolada em funções puras e coberta por testes unitários.

## Limites deliberados

- nenhuma previsão de fechamento é gerada;
- nenhuma recomendação automática é inferida a partir de correlação;
- os padrões não alteram o Opportunity Score;
- dados ausentes reduzem a cobertura exibida em vez de serem inventados;
- nenhuma mensagem, ação ou mudança de estágio é executada a partir da tela de inteligência.

## Compatibilidade

Sem migration, nova tabela ou alteração das regras de Score, Pipeline, Radar, automações, vendas ou atividades comerciais.
