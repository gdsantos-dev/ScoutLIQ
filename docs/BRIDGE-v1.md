# ORLIQ Bridge v1

`orliq.bridge` é o contrato portátil de handoff entre o ScoutLIQ e outros produtos do ecossistema ORLIQ. A v1.29.0 somente gera o pacote localmente: não existe sincronização silenciosa, webhook automático ou compartilhamento de credenciais.

## Envelope

Todo pacote contém:

- `schema: "orliq.bridge"`;
- `schema_version: 1`;
- `producer.product` e `producer.version`;
- `target.product` e `target.profile`;
- `generated_at` em ISO 8601;
- metadados mínimos do workspace;
- `summary` com contagens e agregados monetários;
- `data` com o payload do perfil escolhido.

## Perfis

### `workspace`

Handoff amplo para o ecossistema ORLIQ. Pode conter três escopos independentes:

- `commercial`: negociações, estágio, Opportunity Score, contexto principal e próxima ação;
- `delivery`: vendas fechadas e andamento da entrega;
- `finance`: valores vendidos, recebidos, a receber, recorrência e pagamentos.

### `finance` para DashLIQ

Perfil reduzido com vendas, pagamentos e recebíveis. O contrato não presume que o DashLIQ atual já possua importador para este arquivo. O objetivo da v1 é fixar um formato estável para que o consumidor possa ser implementado depois sem acoplar os bancos dos dois produtos.

## Privacidade

- dados de contato são opt-in;
- notas internas de leads não entram no Bridge v1;
- senhas, tokens, cookies, `.env` e configurações privadas nunca fazem parte do pacote;
- nenhum arquivo é enviado automaticamente pelo ScoutLIQ.

## Dinheiro

Valores monetários usam inteiros em centavos e carregam a moeda explicitamente. Nenhuma conversão cambial é feita durante o handoff.

## Compatibilidade

Consumidores devem rejeitar versões de schema que não conhecem e ignorar campos adicionais desconhecidos dentro de uma versão conhecida. Mudanças incompatíveis exigem novo `schema_version`.
