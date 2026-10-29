# ScoutLIQ v1.19.0 - Research & Automation 2.0 · Parcela 4/4

Quarta parcela e fechamento da fase Research & Automation 2.0, construída sobre a v1.18.0.

## 1. Sinais combinados

A Score Engine passa a expor padrões compostos quando evidências independentes apontam para a mesma situação comercial. Esses sinais são explicativos e não adicionam pontos ocultos ao Opportunity Score.

Padrões iniciais:

- demanda local forte com presença digital abaixo do mercado;
- crescimento recente sem evolução digital equivalente;
- piora digital com demanda pública existente;
- operação aparente estruturada com lacuna digital relevante;
- fit forte + confiança suficiente + canal de contato disponível.

Cada sinal apresenta evidências e uma ação comercial sugerida. Automações também podem usar `combined_signal` como condição com o operador `contains`.

## 2. Campanhas e atribuição

Nova área **Campanhas** para agrupar empresas sob uma hipótese ou estratégia de aquisição.

Uma campanha pode:

- nascer vazia ou a partir do snapshot de uma busca salva;
- receber/remover empresas manualmente;
- ser marcada como ativa, pausada ou encerrada;
- acompanhar empresas, contatadas, respostas, negociações, perdas e vendas atribuídas;
- mostrar receita e recorrência atribuídas por moeda.

A atribuição de receita é explícita: uma venda pode apontar para uma campanha. Quando uma empresa pertence a exatamente uma campanha ativa e a venda não informa campanha manualmente, o Scout atribui automaticamente a essa campanha. Se houver ambiguidade, a venda fica sem atribuição em vez de adivinhar.

## 3. Aprendizado descritivo por ganhos/perdas

Ao fechar uma venda ou marcar uma oportunidade como perdida, o Scout salva um snapshot compacto da qualificação naquele momento. Isso impede que mudanças posteriores no site ou nos dados reescrevam o contexto histórico do desfecho.

Com base mínima de seis negociações fechadas, contendo pelo menos dois ganhos e duas perdas, a área Campanhas passa a mostrar padrões descritivos em dimensões como:

- nicho;
- volume de avaliações;
- situação do site;
- faixa do Opportunity Score;
- Timing;
- estrutura comercial aparente;
- melhor fit por serviço.

O sistema mostra amostra, ganhos, perdas, taxa observada e diferença em pontos percentuais contra o histórico geral. Esses padrões **não alteram automaticamente a Score Engine** e não são apresentados como previsão de fechamento.

## Banco e exportação

- migration Alembic: `018`;
- novas tabelas: `campaigns` e `campaign_leads`;
- `sales` ganha `campaign_id` opcional;
- `leads` ganha `outcome_snapshot_json` e `outcome_recorded_at`;
- exportação sobe para `schema_version: 13` e inclui campanhas, membros, snapshots e insights de desfecho.

## Validação

- suíte backend: 97 testes passando;
- Alembic: `018` é o head;
- Score Engine payload: `2.5`;
- arquivos TS/TSX alterados passam por transpile sintático do compilador TypeScript;
- CSS validado com parser `tinycss2` sem erros;
- dicionários EN-US e ES sem chaves duplicadas;
- o `npm ci` deste ambiente falhou com erro interno do próprio npm (`Exit handler never called!`), portanto o build Vite completo deve ser confirmado no Railway.
