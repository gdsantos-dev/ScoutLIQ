# Busca unificada — contrato v1.37

Os endpoints herdados continuam disponíveis por adaptadores do serviço compartilhado.
Ver SEARCH-COMPATIBILITY-v1.37.md para contratos síncronos e jobs persistentes.

## Catálogo

`GET /api/smart-searches/locations?q=Recife&country=BR&lang=pt`

Exige sessão autenticada. Consulta de 2–160 caracteres, país ISO opcional e
idioma pt/en/es. Limite de 30 consultas/minuto por usuário. Resultado: seleção
administrativa com ID, nome, nome formatado, tipo, país, componentes regionais,
fonte e timestamp; coordenadas/bbox somente quando a fonte fornece.

Geoapify pode resolver bairro/distrito, cidade, região, estado e país. Fallback
IBGE resolve município brasileiro; não fabrica limites nem coordenadas.
Uma bbox é envelope, não polígono administrativo. Falha de catálogo é 503,
não lista vazia fictícia. O frontend aguarda 350 ms sem digitação.

## Lançamento

`POST /api/smart-searches/launch`

```json
{
  "text": "Hamburguerias",
  "location": {"id": "ID_FORNECIDO_PELO_CATALOGO", "query": "Recife", "country": "BR"},
  "target": 50,
  "request_key": "UUID_GERADO_PELO_CLIENTE",
  "confirm_location": false
}
```

O servidor resolve novamente o ID exato no catálogo; não aceita coordenadas ou
rótulos arbitrários como localização autorizada. Não escolhe o primeiro homônimo.
Quantidades válidas: 25/50/75/100. Limite de 6 lançamentos/minuto/usuário.
Usa `SmartSearch`, worker, limites e recuperação existentes.

Respostas 200 discriminadas:

- `started`: job criado ou recuperado por idempotência.
- `location_conflict`: o pedido menciona outra área; corrigir o texto ou
  reenviar com `confirm_location=true` após escolha explícita.
- `clarification`: critérios não reconhecidos; não cria job incompleto.

Erros relevantes: 401 sem sessão, 422 seleção/quantidade inválida, 409 conflito
de chave, worker não configurado ou limite de buscas abertas. Payloads extras
são rejeitados por schema. A chave é exclusiva por usuário. O hash do payload
inclui texto/local/quantidade, mas exclui a chave e a confirmação do conflito.
Disputa na restrição única faz rollback e recupera o vencedor; payload diferente
continua retornando 409.

## Área explícita do mapa

O mesmo `/launch` aceita `area` em alternativa a `location`. Exatamente uma
delas é obrigatória. `area` contém `kind: bounds|polygon`, `bounds: [oeste,sul,leste,norte]`
e `polygon: [[longitude,latitude],…]`. Não representa um município confirmado.
O backend deriva centro/raio, limita a 25 km, exige coordenadas finitas e limites
ordenados. Polígonos têm 3–32 pontos distintos, área não nula, sem cruzamentos;
o envelope deve corresponder aos pontos. Campos extras são recusados.

A geometria participa do hash idempotente, do job, da busca salva e da rotina.
Texto geográfico conflitante requer confirmação explícita. O modelo semântico
não pode produzir `area` nem `location`; a seleção autorizada é reaplicada após
interpretar. `market` permanece vazio: coordenadas não provam cidade/país.

Geoapify coleta o círculo envolvente e a persistência compartilhada recorta os
resultados pelos limites/polígono exatos. Resultados sem cidade/município e país
observados são recusados. OSM não declara suporte a essa área nesta versão;
retorna limitação sem chamada externa. Cobertura real continua não homologada.

## Interpretação e custos

`POST /api/smart-searches/prepare` é o preview **opcional**, determinístico e
autenticado. Recebe texto/quantidade e retorna intenção, setores suportados e
avisos não geográficos. Abrir “Ajustar critérios” não inicia job nem usa modelo.

Launch pode receber `criteria`: setores (1–4), perfil tipado,
requisitos/preferências, exclusões e combinação `all`/`any`.
Campos extras são rejeitados; setores/exclusões são conferidos no contrato
existente. A intenção inteira é revalidada após compor os ajustes, inclusive
o objeto Profile. Não usar `model_copy(update=...)` com dicionário de perfil.

Se houver texto não interpretado, `accept_unresolved=false` mantém a pendência.
O usuário precisa marcar explicitamente que deseja aplicar somente os critérios
exibidos para aceitar ignorar esses trechos. Aceitar a pendência não autoriza
setores arbitrários, geografias forjadas, campos privilegiados ou novos custos.

Determinística por padrão. `SCOUT_SEMANTIC_AUTO_POLICY=complex_only` permite tentar
semântica somente diante de pendência e com a configuração existente completa:
habilitação, credencial, modelo, preços e orçamentos. Semântica não pode fornecer
localização resolvida; a seleção autoritativa é reaplicada no servidor.
Fallback e ledger de interpretação existentes são reutilizados.

Autocomplete usa cache isolado por usuário e reservas persistentes no ledger existente,
com limites diários globais e por usuário, além de rate limit e debounce. A migração
027 adiciona cache e gate transacional. Falhas também consomem a reserva; os limites
e preços reais do provedor ainda exigem homologação externa. Ver LOCATION-CONTRACT-v1.37.md.

## Coleta e compatibilidade

Geoapify recebe o `place_id` escolhido no filtro administrativo, sem nova
geocodificação aproximada. Categorias de hamburgueria são específicas.
Adaptadores precisam declarar capacidade para a seleção. OSM/IBGE sem fronteira
compatível produz resultado parcial e motivo explícito; não vira raio de 5 km.
Limites de páginas, prazo e orçamento não permitem afirmar coleta exaustiva de
estado ou país.

`Intent.location` é JSON opcional. Intenções antigas sem esse campo continuam
válidas; buscas salvas e rotinas mantêm o campo quando presente. A migração 027
é aditiva; revisões históricas permanecem intactas. Entradas históricas preservam
filtros e geometria por adaptadores compartilhados. Área visível, polígono, buscas
salvas e monitores usam o worker existente; o endpoint síncrono mantém seu contrato
pelo coletor comum. Ver a matriz de compatibilidade para os limites de cada caminho.

## Resultados e revisão

Plano, cobertura, prazo e limites efetivos do job estão em “Detalhes da execução”
no progresso, recolhidos por padrão. Não são novos controles de configuração.

No lançamento com geografia validada, avisos geográficos conhecidos do modelo
são descartados antes de reaplicar a seleção de catálogo/mapa. Os demais avisos
permanecem. Os endpoints legados de interpretação sem seleção continuam emitindo
suas solicitações de cidade/país; não recebem confirmação geográfica automática.

Salvar no progresso reutiliza `POST /smart-searches/{id}/save`. Reabrir uma busca
comercial salva preenche o formulário único e conserva todos os critérios, sem
rederivá-los do texto. Intenção antiga sem localização resolvida exige seleção
no catálogo; nunca usa por conveniência outro local lembrado no navegador.

Oportunidades/Monitoramentos usam o mesmo formulário e encaminham o job ao Radar.
Resultados de rotina também abrem o Radar pelo ID persistido. Não há nova coleta
ao abrir esses resultados. A matriz `SEARCH-COMPATIBILITY-v1.37.md` identifica
os adaptadores territoriais consolidados no backend.

Detalhe do job inclui `lead` canônico, Score existente e grupo. Lista/mapa usam
esses registros, sem segundo índice. Histórico recupera o mesmo ID persistido.
Grupos: qualificadas, em investigação e descartadas; “todos” reúne os resultados.

A ficha, aba Análise, usa `POST /api/smart-searches/leads/{id}/review` existente:
versão, autonomia, operação, modelo comercial, porte, natureza e justificativa
de 10–500 caracteres quando altera fatos. confirm_existing permite apenas confirmar
os mesmos campos, reutilizando justificativa existente ou a avaliação exibida;
não transforma desconhecido em confirmado. A revisão registra atividade e reclassifica jobs do usuário.
Propriedade e versão são verificadas no backend. O frontend notifica o progresso
aberto para reler os grupos após uma revisão; não recalcula classificação local.

## Limites de validação

Fixtures locais não comprovam veracidade dos estabelecimentos, cobertura real,
precisão comercial, custo real ou autorização de contato. Nenhuma nova autorização
de envio foi adicionada. Ver VALIDATION-v1.37.md e LOCATION-CONTRACT-v1.37.md para custo/cache.
