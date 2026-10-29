# Rotinas, permissões e consumo — P0.1

## Uso

Salve uma intenção na Busca inteligente e abra Automações → Rotinas de pesquisa. Configure objetivo, frequência e limites. Ativar agenda para o próximo intervalo; “Agendar agora” solicita uma execução imediata, respeitando os mesmos limites. Salvar pausada não executa. Pausa é reversível enquanto o prazo da execução permitir; cancelar conserva o resultado parcial. Para mudar critérios durante execução, cancele primeiro e reconfigure.

São implementados dois objetivos:

- **Descobrir novas oportunidades:** cria um SmartSearch com a intenção congelada, fonte configurada e orçamento. Empresas já qualificadas pela rotina ou presentes no pipeline não voltam como descoberta inédita. Opt-out do lead permanece impeditivo. Duas páginas sem novas identidades encerram a coleta repetitiva.
- **Atualizar investigações vencidas:** considera até 1.000 leads próprios não demo, não bloqueados, fora de ganhos/perdidos; cruza cidade/país/setor, adequação e requisitos conhecidos. Ordena pelo Score 3.0 e usa ResearchBatch web ou deep. Dados desconhecidos continuam passíveis de investigação, não viram fatos negativos. Região textual não subdivide a cidade. Não é um monitor de alteração de cada página nem prova de cobertura integral da carteira.

Pesquisa recente é reutilizada pelo prazo configurado, padrão sete dias. Um job aberto por rotina; uma rotina equivalente ativa/pausada por conta. Agendamento atrasado gera uma execução, sem recuperar todos os intervalos perdidos. A configuração persiste até seu limite total de execuções. Critérios editados na pesquisa original não alteram silenciosamente a autorização da rotina: reconfigure para capturar a nova intenção.

## Limites

| Limite | Padrão | Intervalo permitido |
|---|---:|---:|
| Frequência | 24 horas | 24–720 horas; interface diária/semanal/30 dias |
| Tarefas por execução / dia da rotina | 20 / 40 | 1–100 / 1–200 |
| Operações por execução / dia da rotina | 100 / 150 | 1–500 / 1–1.000 |
| Páginas / candidatas / investigações | 3 / 100 / 15 | 1–12 / 25–600 / 0–50 |
| Reinvestigar após | 7 dias | 1–90 |
| Prazo | 60 minutos | 15–120 |
| Total de execuções | 30 | 1–365 |

O executor global conserva 100 tentativas/dia UTC por padrão (`RESEARCH_DAILY_BUDGET`). `RESEARCH_HTTP_DAILY_BUDGET=500` limita operações dos adapters dentro do worker. Limites por adapter: Geoapify 100, OSM 100, Brave 100, website 400; configuráveis via `RESEARCH_PROVIDER_DAILY_LIMITS`. Provider omitido desse objeto recebe cota zero. A reserva é persistida antes da operação e serializada pelo mesmo token global. Tentativas fracassadas/reservadas consomem cota; reiniciar processo não reinicia o orçamento.

**Operação de adapter não é unidade faturada nem necessariamente uma requisição HTTP:** pode incluir redirecionamentos. Tarefas podem realizar várias operações. Chamadas manuais/legadas fora do escopo do worker não entram neste ledger e continuam sob os limitadores existentes; estas cotas não são um teto financeiro de toda a instalação. Cache de fonte permanece sujeito ao contrato já existente. Não há cache externo novo.

Valores monetários estimado/confirmado são `null`, estado `unknown`. A interface informa consumo sem inventar preço. Nenhuma IA paga obrigatória. Cota excedida interrompe o trabalho, conserva registros e mostra motivo. Três tentativas, backoff exponencial e timeouts anteriores permanecem; pesquisas em curso podem consumir uma operação já iniciada após um pedido de cancelamento, mas não devem gravar resultados com token invalidado.

O ledger registra conta, token, trabalho, adapter, estado e horário, sem URL, conteúdo externo ou credencial. Histórico acompanha a vida da pesquisa; excluir a pesquisa cancela filhos e remove sua configuração/histórico. Tentativas continuam vinculadas à conta, sem o vínculo de rotina excluído; excluir a conta remove seus dados. Não há retenção infinita contratual nem limpeza automática de histórico nesta fatia. Heartbeats de outros processos vencidos há mais de um dia são removidos.

## Contratos e estados

`/api/operations/routines`: listar; `/{id}/configuration`: configurar; `/{id}/control`: pausar/retomar/cancelar/agendar; `/{id}/history`: histórico; `/status`: consumo, disponibilidade e últimas interrupções. Rotas privadas validam conta e CSRF nas mutações; DTOs rejeitam campos extras. A versão otimista evita sobrescrever configuração com tela antiga.

Rotina: disabled, active, paused, cancelled, completed, blocked. Execução: running, paused, completed, partial, cancelled, skipped. Falta de fonte/capacidade tem motivo explícito. A interface conserva as cinco execuções mais recentes por rotina; histórico retorna até 100 eventos. Execuções anteriores permanecem no banco. Não há alegação de central completa de conversas/decisões nesta entrega.

## Matriz de autonomia e elegibilidade

| Ação | Nível | Condição nesta fatia |
|---|---|---|
| Descoberta, deduplicação e pesquisa | Automático | Rotina explicitamente ativa, escopo/limites, fonte e conta válidos |
| Atualização de evidências e prioridade | Automático | Resultado permitido e token vigente; mesmo serviço de evidência/Score 3.0 |
| Reclassificação incerta e revisão comercial | Assistido | Revisão humana com motivo/versionamento existentes |
| Regras, tarefas e rascunhos existentes | Automático/assistido conforme regra | Nenhum agendamento novo de preparação/follow-up nesta fatia |
| Aprovação do conteúdo de rascunho | Supervisionado | Destinatário, canal, evidências e conteúdo continuam vinculados à aprovação existente |
| E-mail/WhatsApp | Supervisionado e indisponível | Integração oficial/outbox ainda não implementadas; inserir credencial não habilita envio |
| Alteração financeira/negociação irreversível | Supervisionado | Nenhuma permissão automática nova |

Prioridade comercial não comprova elegibilidade de contato. Recusa por destinatário permanece válida mesmo em outro lead da conta/canal. Websites e mensagens são dados não confiáveis e não alteram essas permissões.
