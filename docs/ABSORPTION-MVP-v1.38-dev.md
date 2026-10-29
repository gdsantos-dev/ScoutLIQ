# ScoutLIQ • Absorção externa • v1.38-dev em integração (não homologado)

Base: fonte completo v1.37.0 enviado em 23/10/2026. Implementação isolada de **entrada em lote com confirmação explícita**, sem mudança de Score 3.0, busca, CRM, worker ou envio. **Não é release de produção.** Nenhum deploy, credencial externa ou banco pessoal foi usado.

## UX

Em **Gerenciar → Negociações → Absorver pesquisa**, cole ou carregue JSON. Aceita um array de até 50 objetos ou `{ "records": [...] }`. Prévia persistida exibe prontos, pendentes e duplicados; confirmar só grava os prontos no **Lead canônico**, visível no Radar. Pendentes continuam no histórico; para corrigir, altere seu JSON e crie novo lote. Busca automática e envio comercial não são acionados. Até 200 lotes por conta.

## Campos

`name` obrigatório. `category`, `city`, `country` (ISO-2, BR por padrão), `address`, `latitude`, `longitude`, `rating`, `reviews`, `website`, `instagram`, `phone`, `whatsapp` (código do país e dígitos), `contact`, `notes`, `source_url`, `source_id`, `claims` opcionais. Até 6 `claims`: `{ "statement": "...", "source_url": "https://..." }`. Fontes externas são **alegações não verificadas**; os claims ficam no histórico da ficha e **não se tornam OpportunityEvidence confirmado**, diagnósticos de site ou justificativa de disparo.

```json
[
  {
    "name": "Cafeteria Exemplo",
    "category": "Cafeteria",
    "city": "Recife",
    "country": "BR",
    "latitude": -8.05,
    "longitude": -34.90,
    "source_url": "https://example.org/local",
    "claims": [{ "statement": "Contato encontrado no site indicado", "source_url": "https://example.org/local" }]
  }
]
```

Coordenadas não são inventadas. Sem cidade, categoria ou par latitude/longitude, a ficha fica **pendente**. Estado de site importado sempre começa `unknown` e `instagram_active=false`. A deduplicação conservadora usa ID de origem ou **nome+cidade+país** com endereço, telefone ou coordenadas correspondentes, evitando confundir filiais pelo nome. Revalida no commit. O lote usa UUID de requisição, hash do payload, autorização do proprietário e transação única com claim atômico de status; repetir a confirmação do mesmo lote retorna o recibo.

## API

- `POST /api/absorption/preview` `{request_key,source,records}` cria prévia persistente sem criar Leads.
- `GET /api/absorption/batches` últimos 30 lotes do usuário.
- `GET /api/absorption/batches/{id}` detalhes e recibo próprios.
- `POST /api/absorption/batches/{id}/commit` `{payload_hash,confirm:true}` confirma os prontos, guarda proveniência em `LeadActivity` e não gera outreach.

Migração aditiva **028**, duas novas tabelas (`absorption_batches`, `absorption_items`); downgrade recusa apagar lotes persistidos. O endpoint geral limita JSON a 64 KiB, a UI a 48 KiB. A interface aceita **JSON**, não faz parsing de CSV nesta etapa. O campo `source:'csv'` existe no contrato para integração posterior, não representa importação de CSV bruto.

## Validação e fronteiras

O PATCH experimental não havia concluído build/E2E. A integração local e seus resultados estão em [INTEGRATION-v1.38-dev.md](INTEGRATION-v1.38-dev.md). Não reutilizar as declarações históricas da v1.37 como testes da v1.38.

Serialização transacional por usuário cobre prévias e confirmações, inclusive entre lotes distintos, sem alterar permissões nem criar outro worker. Leituras do recibo são por proprietário. Há limites de 12 prévias e 12 confirmações/minuto por usuário, além do limite de escrita global herdado. O retry de prévia mantém o UUID enquanto o payload não muda. Categoria/cidade com menos de dois caracteres permanecem pendentes; linhas pendentes não bloqueiam linhas completas posteriores. Telefones compartilhados não fundem registros com endereços divergentes. IDs de origem continuam exigindo consistência do importador; deduplicação avançada fica para a próxima etapa.

O downgrade recusa apagar qualquer lote persistido, mesmo sem itens. Para reverter o código após uso, preserve um backup consistente do banco e dos fontes; não apague tabelas para contornar essa proteção. O histórico de staging não integra ainda o export geral: preserve o banco completo e consulte os endpoints de lotes. Os registros importados e suas atividades já participam do export canônico.

## Próximas fatias

1. Corrigir pendências com geocodificação/fonte autorizada, sem lat/lng inventados; importar CSV real usando parser robusto e revisão por registro.
2. Conectar absorção ao worker/research existente por jobs limitados, com custo/cota, provedores e consentimento controlados. Pesquisa externa não promove diagnósticos sem verificação.
3. Encaixar priorização e triagem em lote no mesmo Gerenciamento/CRM e reusar a fila/outbox com aprovação humana antes de qualquer contato.

Não remodelar o motor de score, duplicar CRM ou criar uma segunda aplicação.
