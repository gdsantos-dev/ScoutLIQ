# Operação da inteligência P0.2

## Interpretação opcional

O modo determinístico é padrão. Para habilitar a opção semântica, configure no backend `SCOUT_SEMANTIC_ENABLED=true`, `SCOUT_SEMANTIC_MODEL`, `SCOUT_SEMANTIC_API_KEY`, `SCOUT_SEMANTIC_DAILY_TOKENS` e `SCOUT_SEMANTIC_USER_DAILY_TOKENS`. Zero ou configuração incompleta desabilita. Não existe modelo ou orçamento pago implícito. A disponibilidade daquele modelo e seu suporte ao schema precisam ser homologados na conta do operador.

O usuário escolhe Semântica na Busca inteligente. Somente o pedido digitado e a meta são enviados; não são transmitidos cadastros, fotos, evidências, mensagens, dados de conta ou credenciais de outras integrações. Evite dados pessoais no texto livre. `store=false` solicita que a resposta não seja armazenada para recuperação pela API; isso não é promessa de retenção zero pelo provedor. Referência oficial consultada: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Requisição HTTPS para origem fixa; redirecionamentos recusados; timeout 20 s; resposta máxima 128 KiB; sem retry automático. Schema limita os campos. Validação local recusa setores/exclusões inválidos, alteração da meta/pedido e localização sem âncora textual. País inferido requer confirmação. Critérios numéricos não executáveis continuam pendentes. Isso valida o contrato, não prova que toda interpretação é comercialmente correta: o resumo deve ser revisado antes de executar.

## Consumo

Uma reserva conservadora soma bytes UTF-8 do payload, 4.096 tokens de margem e teto de saída (512–4.096; padrão 2.048). O limite diário global e o limite por usuário são aplicados na mesma transação serializada antes de chamar a API. O total informado pelo provedor é guardado separadamente; se exceder a reserva, contabiliza-se o maior valor e o resultado não é aceito. A contagem por bytes é uma aproximação conservadora, não medição de tokenização ou garantia de preço da fatura.

`semantic_attempts` guarda hash do pedido, modelo, estado, reserva e uso informado. Não guarda texto do pedido, resposta bruta, chave ou erro externo. `reserved` pode significar processo interrompido durante a chamada: a reserva permanece, inclusive após reiniciar. Repetir o mesmo request_key não faz outra chamada; retorna o fallback. Não são reenviadas requisições incertas. Fechar o modal não cancela uma chamada já recebida pelo provedor. Não há cobrança recorrente de modelo por rotina.

Custos monetários permanecem desconhecidos: o operador precisa consultar os preços e a fatura da sua conta. Configure também o limite de gasto no provedor. Não confundir a nova reserva de tokens da prévia com o ledger de operações de adaptadores do worker de P0.1, que continua intacto.

## Descoberta e investigação

O plano usa somente as capacidades do adaptador efetivamente configurado, sem trocar credenciais/provedores. Cursores, resultados, motivo da decisão e contadores persistem no SmartSearch. Jobs antigos sem plano mantêm o cursor anterior. Pausa/cancelamento/lease/orçamento e rotinas passam pelo executor e pelo ResearchBatch existentes. A alocação adapta o esforço de coleta; não acrescenta pontos às empresas.

Não foram adicionadas fontes, scraping de redes sociais ou coletas autenticadas. O enriquecimento usa páginas públicas já obtidas pelo WebsiteResearcher, com seus controles de destinos e redirecionamentos. A auditoria mantém o limite de quatro páginas, do mesmo site. O operador deve ter direito de usar as fontes e observar seus termos. Não é feita uma certificação jurídica dos termos de cada website.

Os contatos observados têm URL, método e instante. Links públicos não comprovam consentimento, titularidade de uma pessoa, existência de caixa postal, funcionamento do formulário nem atividade recente da empresa. Não há inferência de nomes, e-mails prováveis ou decisores. Quando há divergência, os valores permanecem na ficha para revisão. Evidências contextuais são técnicas e limitadas às páginas consultadas; não substituem qualificação humana.

## Avaliação

Execute `python scripts/evaluate_commercial_quality.py` para gerar `artifacts/commercial-quality.json`. Os sete cenários foram herdados da base e não foram rotulados como casos reais da ORLIQ. Score 3.0 e seleção ficaram idênticos ao baseline: TP=1, FP=0, FN=0, TN=6; precisão/recall=1 no conjunto minúsculo sintético, NDCG@10=1, precisão nos sete itens disponíveis=1/7. Não há ganho medido, amostragem representativa, revisão humana ou resultado de vendas. Essas métricas são prova técnica de preservação, não taxa comercial anunciável.
