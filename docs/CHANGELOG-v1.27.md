# ScoutLIQ 1.27.0 — Outreach assistido + templates

A v1.27.0 evolui a Execução Comercial sem criar automação de disparo. A fila de Ações passa a ajudar a preparar contato, mantendo revisão humana antes de abrir WhatsApp ou e-mail.

## O que entrou

- compositor de contato dentro de Ações;
- canais WhatsApp e e-mail;
- quatro templates padrão para primeiro contato e follow-up;
- biblioteca de templates editável, com criação, edição, exclusão e restauração dos padrões;
- armazenamento local isolado por conta, sem migration e sem tabela nova;
- variáveis reutilizáveis para empresa, contato, cidade, categoria, site, Opportunity Score, serviço com maior fit, principal oportunidade e próxima ação;
- preenchimento factual usando apenas dados já presentes no lead, Score Engine e enriquecimento;
- prévia totalmente editável antes de qualquer abertura de canal;
- cópia para área de transferência;
- abertura de WhatsApp com texto preenchido e e-mail com assunto/corpo preenchidos;
- registro manual como enviado, separado da abertura do canal;
- nenhuma mensagem é enviada automaticamente.

## Segurança de produto

Abrir um canal externo não cria atividade automaticamente. O usuário registra o envio somente depois de confirmar que realmente enviou. Isso evita histórico comercial falso.

## Compatibilidade

Backend, migrations, banco, Score Engine, Radar, automações e regras comerciais permanecem intactos.
