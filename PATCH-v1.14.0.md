# ScoutLIQ v1.14.0 — Score Engine 2.0 · Parcela 4/5

## Escopo

Esta versão entrega as melhorias 7 e 8 da Score Engine 2.0:

1. Reanálise inteligente quando a cobertura das evidências estiver baixa ou desatualizada.
2. Contexto competitivo local com amostra mínima antes de interferir no score.

## Reanálise inteligente

Novo endpoint `POST /api/leads/{id}/reanalysis`. Ele inspeciona a cobertura atual e escolhe a menor sequência útil:

- pesquisa web quando a identificação/site ainda não foi verificada ou está desatualizada;
- auditoria profunda somente quando há website confirmado e a auditoria é inexistente/desatualizada;
- atualização do contexto competitivo a partir da base atual do Radar;
- nenhuma chamada cara quando as evidências recentes já estão suficientes.

A resposta informa `before_confidence`, `after_confidence`, ações executadas e os dados atualizados. A interface oferece **Aprofundar análise** diretamente dentro do Confidence Score.

## Contexto competitivo local

O Scout compara a oportunidade com estabelecimentos do mesmo nicho e país:

- tenta primeiro raio de 5 km;
- expande para 10 km se houver menos de quatro pares;
- usa no máximo 30 pares próximos;
- exige pelo menos 4 empresas comparáveis e 3 estados de site conhecidos para marcar a amostra como utilizável;
- calcula presença de site próprio, proporção de sites fortes, mediana de avaliações, mediana de nota e posição relativa em avaliações;
- detecta lacuna quando o negócio está sem presença própria em um mercado onde a maioria possui site, ou quando o site está fraco em um mercado com forte presença digital.

O contexto **não cria necessidade sozinho**. Ele apenas pode reforçar a dimensão `digital_need` quando a lacuna local está sustentada por amostra suficiente.

## Score Engine

Versão interna das regras: `2.3`.

Novos motivos possíveis:

- `competitive_site_gap`
- `competitive_demand_gap`

O teto geral continua em 100 pontos e as quatro dimensões permanecem inalteradas.

## Persistência

Migração Alembic `013` adiciona ao lead:

- `competitive_context_json`
- `competitive_analyzed_at`

A exportação passa para `schema_version: 8`.

## Validação

- suíte backend: 78 testes passando;
- Alembic: `013` como head;
- Python compilado sem erros;
- TS/TSX alterado validado sintaticamente;
- CSS sem erros de parsing;
- build Vite completo depende da instalação das dependências npm no ambiente.
