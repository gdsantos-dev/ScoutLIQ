# Próxima evolução — mapa técnico, não implementado

Base após integração: v1.38-dev, migração 028. Este documento não autoriza envios nem altera Score 3.0.

| Capacidade | Pontos existentes a reutilizar | Alteração necessária e critério de aceite |
|---|---|---|
| CSV e texto tabular | ResearchRecord/AbsorptionPreview em backend/absorption.py; AbsorptionDialog.tsx | Parser local limitado a 50 linhas, tamanho limitado antes de parse, vírgula/ponto e vírgula, aliases e revisão de mapeamento. Preservar erros por linha sem descartar as válidas. source=csv hoje é apenas metadado: não existe parser CSV. |
| Correção individual | AbsorptionItem.payload_json, classify, owned_batch, lock_absorption | Endpoint com DTO restrito, versão otimista por item/lote, histórico de alterações e nova assinatura da prévia. Recalcular elegibilidade e duplicidade dentro da transação. Itens importados não podem ser recriados. Lote committed hoje é recibo imutável; não basta liberar o botão. |
| Resolver pendências | locations.py, location_budget.py, providers.py; campos opcionais ResearchRecord | Ação explícita e limitada, orçamento/reservas antes de I/O. Catálogo administrativo não identifica estabelecimento: nunca usar centro de município como coordenada comercial. Confrontar nome, cidade, endereço, contatos e origem; múltiplas correspondências exigem seleção. Manter desconhecido quando não houver confiança. |
| Enriquecer contatos | enrichment.py: start_profile/apply_values/record_attempt; adaptadores existentes | O enriquecimento atual parte de um Lead válido. Criar adaptação restrita para staging, sem Lead fictício nem promoção de alegações. Registrar fonte, tentativa, confiança e consumo; retornar pendência quando indisponível. |
| Pesquisa pós-absorção | AbsorptionItem.lead_id, atividade external_absorption, main.create_research_batch, ResearchBatch/ResearchBatchItem e research_worker.claim | Associar os IDs importados a um lote canônico de pesquisa, com consentimento/configuração, cotas, idempotência, cancelamento e recuperação existentes. Não criar outro worker. Nenhuma pesquisa é disparada nesta integração. |
| Triagem e priorização em lote | Lead canônico, Score/CommercialFit, grupos e Análise existentes | Usar resultado canônico e evidências com estado explícito; criar operações de seleção/revisão limitadas e autorizadas, sem novo score. Qualidade real depende de casos revisados ORLIQ. |
| Dedupe avançado | classify/same_company/external_identity | Combinar identidade com domínio, contatos normalizados, origem e geografia; separar confirmado/possível. Nunca usar apenas nome ou domínio de rede para fundir filiais. Reavaliar conflitos de source_id e distinguir staging de outro lote de Lead já importado. |

## Busca Unificada sem nicho obrigatório

Remover apenas required do formulário não resolve o contrato:

1. `frontend/src/components/UnifiedSearch.tsx`: hoje o pedido alimenta prepare/launch e critérios por setor. Tornar nicho opcional deve manter localização explícita, meta e limites; distinguir procura ampla de um texto que o interpretador não entendeu.
2. `backend/search_intent.py`: `Intent.sectors` aceita lista vazia, mas `interpret` produz pendência quando nenhum setor é reconhecido. É necessário representar intenção ampla de maneira explícita, mantendo compatibilidade de intenções salvas e exclusões.
3. `backend/smart_search.py`: Criteria exige 1–4 setores; validação de lançamento recusa ausência de setores; plano/cobertura e query_for indexam setores, e save usa `intent.sectors[0]`. Adaptar esses caminhos conjuntamente, inclusive retomada e histórico, sem exceções de índice nem expansão silenciosa de custo.
4. `backend/discovery_contract.py`: DiscoveryQuery já admite category vazia, mas isso não prova suporte de cada fonte. `backend/search_sources.py`, `providers.py` e o planejamento adaptativo precisam declarar capacidade de descoberta ampla, limites e cobertura. Hoje vários adaptadores recusam categorias sem seletor específico.
5. `backend/semantic_intent.py`, `discovery_plan.py`, worker e rotinas: preservar orçamento, seleção geográfica autorizada, idempotência e recuperação; não inventar nicho via modelo. A interpretação determinística continua fallback.
6. Testar pedido amplo, texto ambíguo, exclusões, localização administrativa/mapa, fonte incompatível, meta não preenchida, cancelamento, retomada e busca salva antiga. Comparar qualidade comercial com casos reais revisados, separadamente da aprovação técnica.

## Limites atuais que a próxima etapa deve considerar

- JSON inválido por schema rejeita a requisição inteira; este MVP não possui resultado de erro individual para payload estruturalmente inválido.
- Campos faltantes ficam no staging. Categoria/cidade precisam de pelo menos dois caracteres e coordenadas devem vir em par; nenhuma fonte externa é consultada.
- Não há edição, exclusão/arquivamento ou paginação além dos 30 lotes recentes na UI. O teto é 200 lotes por conta. Preservar o banco completo; staging ainda não integra o export geral.
- Origem/alegações e vínculos são persistidos, mas não equivalem a verificação humana. O estado website_status começa unknown.
- A serialização cobre operações de Absorção. Não coordena todos os criadores legados de Lead; garantia global entre diferentes módulos exige evolução explícita do contrato de identidade/concorrência.
- A UI nova está em português; não foi feita tradução en-US/es do módulo. PostgreSQL, dispositivos físicos e produção não foram homologados nesta integração.

Próxima fatia recomendada: parsing CSV + correção individual versionada, mantendo o staging existente; depois resolução sob demanda. Investigação automática deve entrar pelo worker atual apenas após validar essas entradas.
