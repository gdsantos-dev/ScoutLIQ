# ScoutLIQ v1.5.0 — Deep Site Audit

Base: v1.4.0 Web Research Agent.

## Próximo nível da pesquisa

A pesquisa web continua responsável por encontrar e confirmar o site oficial. Depois da confirmação, o ScoutLIQ agora pode executar uma auditoria profunda e objetiva do site.

### Auditoria multipágina

- Página inicial + até 3 páginas internas relevantes do mesmo domínio.
- Prioriza contato, sobre, serviços, produtos, agendamento e orçamento.
- Mantém as proteções SSRF da v1.4: HTTP(S), portas públicas, IP público, redirects revalidados e mesmo domínio para o crawl interno.

### Sinais avaliados

- Técnico: HTTPS, viewport, tempo de resposta, peso do HTML, mixed content, canonical e favicon.
- Descoberta: title, meta description, dados estruturados, H1 e idioma declarado.
- Conversão: telefone, WhatsApp, e-mail, formulário, CTAs, página de contato e redes vinculadas.
- Acessibilidade básica: idioma, cobertura de alt em imagens, rótulos de botões e presença de H1.

A auditoria não tenta julgar subjetivamente se um site é “bonito”. O resultado é baseado em sinais observáveis.

### Resultado

- Score de saúde do site em 0–100.
- Categorias separadas por função.
- Achados priorizados por severidade.
- Ângulos comerciais derivados apenas dos problemas observados, como conversão, mobile, SEO local e performance.
- Quantidade de páginas verificadas e horário da auditoria.
- `website_status` é atualizado para `good`, `poor` ou `unknown` a partir da auditoria, alimentando o índice de oportunidade já existente.

### Persistência

Nova migration Alembic `007_deep_site_audit.py` adiciona:

- `lead_research.audit_level`
- `lead_research.audit_json`
- `lead_research.audited_at`

Exportação passa para `schema_version: 3`.

### API

Novo endpoint autenticado:

`POST /api/leads/{id}/research/deep`

Se o site ainda não estiver confirmado, o Scout executa primeiro a pesquisa normal. A auditoria só continua após confirmação suficiente da identidade.

## Validação

- 57 testes backend passaram com o timezone da operação (`TZ=America/Sao_Paulo`).
- 24 arquivos TS/TSX: 0 erros de sintaxe no parser TypeScript.
- CSS: 0 erros de parsing.
- Build npm completo continua dependente da instalação completa de dependências no Railway.
