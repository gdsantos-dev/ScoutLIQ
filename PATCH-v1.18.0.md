# ScoutLIQ v1.18.0 — Research & Automation 2.0 · Parcela 3/4

Terceira parcela da fase Research & Automation 2.0, construída sobre a v1.17.1.

## 1. Enriquecimento waterfall

A ficha agora pode executar **Enriquecer dados**. O fluxo tenta fontes em cascata, preservando os valores já conhecidos e só preenchendo lacunas verificáveis.

Ordem atual:

1. dados existentes do lead;
2. detalhes do provedor de origem, quando a fonte suporta consulta individual;
3. pesquisa web, quando ainda há lacunas ou o site não foi verificado.

O Scout persiste, por campo:

- valor;
- fonte;
- confiança;
- data da verificação.

O perfil também guarda tentativas, cobertura total e campos ainda ausentes. Alterações manuais em website/telefone/WhatsApp/Instagram invalidam a proveniência antiga para evitar dados com origem incorreta.

## 2. Motor Trigger → Condição → Ação

Nova área **Automações**.

Gatilhos iniciais:

- score alterado;
- entrada no Pipeline;
- mudança de etapa;
- mudança relevante da Watchlist;
- enriquecimento concluído;
- execução manual pela API.

Condições suportam score geral, Confidence, Timing, fit por serviço, etapa, Pipeline, Watchlist, telefone, WhatsApp, Instagram e situação do site.

Ações iniciais:

- adicionar ao Pipeline;
- definir próxima ação;
- adicionar à Watchlist;
- registrar anotação.

As regras são persistidas e versionadas. Execuções também ficam registradas para auditoria.

## 3. Condições de parada

Cada automação pode parar antes de executar quando:

- o lead alcançar uma das etapas configuradas;
- já existir uma próxima ação, se essa opção estiver ativa;
- a regra atingir o máximo configurado de execuções para aquela empresa.

A parada é registrada separadamente de uma execução bem-sucedida, preservando o motivo.

## Banco e exportação

- migration Alembic: `017`;
- novas tabelas: `automation_rules` e `automation_runs`;
- `leads` ganha `enrichment_json` e `enrichment_analyzed_at`;
- exportação sobe para `schema_version: 12` e inclui regras/execuções; o perfil de enriquecimento segue dentro de cada lead.

## Validação

- suíte backend: 93 testes passando;
- Alembic: `017` é o head;
- Python compilado sem erros;
- TS/TSX alterado passou por validação sintática via compilador TypeScript;
- CSS sem erros de parsing;
- npm/Vite completo não foi validado localmente porque `npm ci` não concluiu no ambiente e deixou dependências externas ausentes.
