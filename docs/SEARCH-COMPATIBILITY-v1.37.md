# Compatibilidade da busca — v1.37

Base exclusiva: FULL v1.36.0, SHA256 `64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75`.

| Entrada | Caminho na v1.37 | Preservação |
|---|---|---|
| Radar, Oportunidades e Monitores | SearchDialog → `/smart-searches/launch` → SmartSearch → worker | Um formulário; acompanhamento no Radar |
| Comando natural e `/` | Mesmo SearchDialog | Texto preenchido; nenhum lançamento involuntário |
| Área visível/polígono | Mesmo launch com SearchArea | Geometria validada, sem município inventado; recorte na persistência |
| Busca comercial salva | Mesmo formulário, com intenção estruturada | Meta, critérios e localização; preview não sobrescreve ajustes |
| Intenção antiga sem localização | Mesmo formulário, exige catálogo | Não herda cidade de outra busca nem escolhe homônimo |
| Busca territorial antiga salva | `/smart-searches/saved/{id}/launch` → create_search | LegacySearch preserva categoria livre, raio, centro, limites e filtros numéricos |
| Monitor territorial | Agendamento existente → SmartSearch no claim existente | Frequência, snapshot, histórico e isolamento; sem nova pesquisa web implícita |
| Rotina comercial | schedule_due → create_search | Limites, ledger, cooldown, histórico e resultados existentes |
| Resultados de rotina | Radar por search_id | Sem iniciar outra coleta |
| `/radar/search` antigo | collect_compatible → search_page → persistência canônica | Resposta síncrona de candidatos preservada; não cria um segundo workflow |
| `/smart-searches` e `/interpret` antigos | Mesmos contratos e serviço | Mantidos para consumidores existentes; sem modos duplicados na UI |

O frontend antigo SmartSearch.tsx, sem consumidores runtime, foi removido. Os endpoints compatíveis permanecem.

## Consultas históricas

LegacySearch é um adaptador de entrada, não um score ou mecanismo novo. Não interpreta categoria livre como outro setor. Mantém rating, reviews, score mínimo, canal, confiança, timing, serviço e problemas. Os filtros são aplicados com monitor_matching, a mesma implementação usada na v1.36. Os registros canônicos continuam em Lead; resultados filtrados ficam no mesmo SmartSearch.

Monitores antigos autorizavam coleta, não investigação adicional de websites. Seu job usa investigation_limit=0 e page_limit=1. Uma reserva expirada consome esse limite conservador: o job termina parcial sem repetir uma chamada possivelmente cobrada. O último snapshot bem-sucedido permanece quando não houve nova coleta. É possível agendar nova execução explicitamente.

Excluir ou desativar um monitor cancela os jobs ligados e invalida leases. Respostas em trânsito não gravam CRM depois do cancelamento. Agendamento é realizado sob o ResearchExecutor existente; não há scheduler paralelo. O ramo antigo de tarefa monitor só permanece para drenagem de claims já existentes durante atualização; não recebe novos claims.

O worker foi adaptado em pontos delimitados: criar jobs de monitores, sincronizar snapshots e usar o coletor compartilhado no ramo de drenagem. Claim, fencing, limites, heartbeat, lotes e outbox continuam existentes. Hashes das adaptações revisadas: REVIEWED-ENGINE-CHANGES-v1.37.json. Score, CommercialFit e outreach mantêm os bytes da base.

## Migração e validação

027 adiciona apenas cache geográfico e seu gate transacional; custos usam WorkAttempt/ProviderOperation existentes. Nenhuma consulta, lead, identidade ou permissão histórica é convertida destrutivamente.

Testes: test_search_compat.py (predicados, idempotência, versão, propriedade, cancelamento e recuperação), test_location_migration.py (026↔027 preservando todas as tabelas anteriores), E2E redesign/smart-search/map-search/autonomy. Ver VALIDATION-v1.37.md para os resultados, sem confundir fixtures com homologação de provedores.
