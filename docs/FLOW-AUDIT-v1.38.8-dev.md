# Auditoria do fluxo — v1.38.8-dev

Base remota confirmada: d8d717a14a03ee60a3f3719881d0fb0553162a4d; revisão 033. Branch codex/v1.38.8-operacao-diaria. Fontes exclusivamente do Git, sem aplicação de ZIP.

| Caminho | Estado observado na base | Intervenção deste ciclo |
|---|---|---|
| ProspectingPlan → PlanDecision → RoutineRun → SmartSearch | Admission, consentimento, ledger e recuperação existentes | Preservar mecanismo; mostrar ligação e motivos |
| SmartSearch → incorporação → investigação automática | `_persist_discovery` enfileirava lote progressivo independente, sem `SmartSearch.batch_id`; os guardas da rotina não identificavam esse lote | Impedir enfileiramento avulso nesse caminho e admitir um lote progressivo canônico vinculado à pesquisa; respeitar limites menores e opt-in atual |
| Meta diária → investigação já admitida | `run_block` encerrava toda a rotina ao atingir incorporações, inclusive investigação já admitida | Meta impede nova descoberta; permitir concluir o lote já admitido dentro de janela, consentimento e orçamento; reclassificar localmente sem nova página |
| ResearchBatchItem → WorkAttempt/ProviderOperation → Lead/Score/evidências | Worker, fencing, política progressiva, persistência e invalidadores existentes | Reutilizar; nenhum novo executor ou Score |
| Lead → CommercialReview → CommercialOperation → OutreachDraft | Prévia, até 50 IDs/versionamento, confirmação, recuperação e compositor canônico existentes | Uma visão diária da mesma fila e das mesmas ações, sem duplicar formulários |
| Respostas → acompanhamento → próxima ação | Associação segura, preferência humana e bloqueios existentes | Reutilizar projeção canônica, sem interpretar mensagens novamente |
| Fila → detalhe → investigação | O detalhe mandava selecionar a empresa novamente | Reutilizar a seleção e sua versão para a operação existente |

Automação progressiva: no máximo um lote por SmartSearch, limitado ao menor teto da busca e da preferência de lote (até 25). Apenas novas empresas não descartadas; reencontros não geram outro lote automático. O restante continua visível para decisão humana, sem expandir autorização. Não há backfill de pesquisas históricas, alteração automática de configurações ou novo serviço.

Visibilidade: em 30/10/2026, tanto o conector quanto a API autenticada reportaram `public`. A documentação de publicação anterior dizia privado. Visibilidade não alterada neste ciclo. O motivo ou momento da divergência não é inferido.

UX: Radar → Fila comercial → Operação do dia, com seleção e operações compartilhadas. Referência de hierarquia: https://styles.refero.design/examples/dashboard-ui-design (contraste para ação, alinhamento previsível e densidade legível); identidade existente preservada, sem remake.

Este documento registra auditoria e desenho; os testes executados e limitações constarão do relatório de validação.
