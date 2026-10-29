# ScoutLIQ v1.11.0 — Score Engine 2.0 · Parcela 1/5

## 1. Score multidimensional

O índice continua de 0 a 100 e continua **não sendo probabilidade de venda**. A regra muda da soma plana para quatro dimensões auditáveis:

- Necessidade digital: 0–50
- Demanda pública: 0–20
- Facilidade de contato: 0–20
- Atividade digital: 0–10

Dados desconhecidos não recebem pontos. Nota pública só pesa quando existe volume mínimo de avaliações. Sites confirmados como ruins recebem peso proporcional à severidade da auditoria quando esse dado está disponível.

## 2. Identificação profunda do site

A análise passa a registrar um perfil compacto e persistido da presença web do lead. Além dos sinais já existentes, detecta de forma conservadora:

- domínio próprio vs. subdomínio de plataforma;
- WordPress, WooCommerce, Elementor, Wix, Shopify, Squarespace, Webflow, Next.js e Bootstrap quando observáveis no HTML;
- Google Tag Manager, Google Analytics e Meta Pixel quando observáveis;
- agendamento;
- e-commerce/checkout;
- catálogo ou cardápio;
- chat no site;
- e-mail, formulário e redes sociais encontrados;
- conteúdo misto e demais sinais da auditoria anterior.

A ausência de uma tecnologia não é tratada como prova de que ela não existe. O sistema só pontua evidência observada.

## Persistência

Nova migração Alembic `012` adiciona `website_intelligence_json` e `website_analyzed_at` aos leads. O perfil completo de auditoria continua em `lead_research`; o lead guarda apenas um resumo estável necessário para pontuar listas e Radar sem consultas extras.

A exportação passa para `schema_version: 7`.
