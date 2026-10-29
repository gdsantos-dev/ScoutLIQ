# ScoutLIQ v1.4.0 — Pesquisa web por evidências

Base: v1.3.0 Region-wide Radar.

## O que entrou

- Pesquisa web por oportunidade no drawer do lead.
- Descoberta direta de domínios prováveis por nome + país, sem chave externa obrigatória.
- Integração opcional com Brave Search (`SCOUT_BRAVE_SEARCH_API_KEY`) para ampliar a descoberta.
- Confirmação conservadora de identidade cruzando domínio, nome, cidade, telefone, endereço e Instagram.
- Auditoria técnica básica do site: HTTPS, viewport, título, descrição, dados estruturados, contatos e tempo de resposta.
- Persistência de confiança, evidências, fontes e data de verificação em `lead_research`.
- Site confirmado atualiza o lead; contatos encontrados só preenchem campos vazios.
- Ausência de evidência nunca vira automaticamente “sem site”.
- Exportação JSON inclui pesquisas web (`schema_version: 2`).
- Proteções SSRF para fetch server-side: somente HTTP(S), portas 80/443, DNS/IP público, redirects revalidados, timeout e limite de corpo.

## Migração

Nova revisão Alembic: `006_lead_research.py`.

O startup normal do Railway executa `alembic upgrade head`.

## Railway

Opcional para busca web ampliada:

```text
SCOUT_BRAVE_SEARCH_API_KEY=<token>
```

Sem essa variável, o ScoutLIQ continua testando e validando domínios prováveis automaticamente.

## Validação

- 54 testes backend passaram.
- 23 arquivos TS/TSX passaram pela validação sintática do compilador TypeScript.
- Dicionários EN/ES sem chaves duplicadas.
- Build npm completo não foi concluído neste ambiente porque `npm ci` não terminou; o Dockerfile/Railway continua sendo a validação final das dependências JS.
