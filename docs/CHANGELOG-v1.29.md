# ScoutLIQ 1.29.0 — Integrações / ORLIQ Bridge

A v1.29.0 cria a primeira fronteira formal entre o ScoutLIQ e o restante do ecossistema ORLIQ sem acoplar bancos, autenticação ou regras internas de produtos diferentes.

## O que entrou

- nova área global **Integrações**;
- contrato portátil `orliq.bridge` schema v1;
- perfil amplo **Ecossistema ORLIQ** com escopos Comercial, Clientes/Entregas e Financeiro;
- perfil **DashLIQ · Financeiro** reduzido a vendas, pagamentos, recorrência e recebíveis;
- resumo do pacote antes da exportação;
- download com extensão identificável `.orliq.json`;
- cópia do payload JSON para clipboard;
- dados de contato opcionais;
- notas internas excluídas do Bridge v1;
- valores monetários mantidos em centavos com moeda explícita;
- documentação do contrato em `docs/BRIDGE-v1.md`;
- lógica de serialização isolada e testável em `frontend/src/ecosystemBridge.ts`.

## Limites deliberados

- nenhum pacote é enviado automaticamente;
- não existe credencial compartilhada entre ScoutLIQ e DashLIQ;
- a v1.29.0 não presume que o DashLIQ atual já tenha um importador para o Bridge;
- nenhuma migration ou alteração de schema é necessária;
- nenhum dado interno como notas, senha, token ou configuração privada entra no payload.

## Compatibilidade

Backend, banco, migrations, Score, Radar, Pipeline, histórico comercial e automações permanecem inalterados.
