# Contrato dos indicadores — v1.38.6-dev

Endpoint autenticado: `GET /api/insights/operations?period=30&origin=all`.
Filtros fechados: períodos `7`, `30`, `90`, `history`; origens `all`, `search`, `absorption`, `manual`.
Não há parâmetros de usuário, IDs arbitrários, SQL dinâmico, provedor de relatório ou telemetria externa.

## Populações e identidade

O período começa à meia-noite local da conta, incluindo o dia atual, e termina no instante da consulta. `history` começa no epoch; eventos futuros são excluídos. Orçamentos existentes continuam usando dia UTC. Pendências são **estoque atual**, independentemente da data de entrada; sua população é indicada em cada linha. As etapas não são uma sequência obrigatória e não devem ser divididas umas pelas outras para inferir conversão.

Empresa única é um `Lead.id` pertencente ao usuário, não demonstrativo. Não há fusão por nome, cidade ou heurística nova. A desambiguação permanece nos mecanismos de descoberta/absorção. Registros de absorção sem vínculo são contados como registros, não como empresas únicas. IDs de empresas excluídas, demonstrativas ou de outra conta não contribuem para o funil. A origem pode ser múltipla: candidato de SmartSearch, vínculo de AbsorptionItem ou source_id `absorption:`, entrada manual e origem de provedor conhecida. A visão consolidada usa união de IDs; somar grupos sobrepostos é incorreto. Origem não reconhecida fica desconhecida, visível na cobertura.

Demonstrações marcadas em Lead são excluídas. Não se deduz que uma empresa é real ou sintética por seu nome. Fixtures de QA usam bancos separados e nunca entram na instalação operacional. Execuções cujo conjunto de candidatos contém somente empresas excluídas ficam fora das métricas de execução. Buscas sem candidatos podem representar trabalho real sem resultado e permanecem observáveis.

## Fontes e definições

| Conjunto | Fonte canônica | Definição e limite |
|---|---|---|
| Encontrados/recebidos | SmartSearch.state_json.candidates + duplicate_records; AbsorptionItem/Batch; Lead manual | Ocorrências rastreáveis de execuções/lotes criados no período. Não usa `discovered/scanned` como empresas: esse contador pode incluir itens sem identidade. Cobertura parcial da descoberta antiga. |
| Únicos | IDs canônicos das ocorrências acima | União deduplicada; itens ainda sem vínculo são exibidos à parte. |
| Duplicatas | entry.origin=duplicate; AbsorptionItem.status=duplicate | Duplicação explicitamente reconhecida. Reencontro de empresa em outra busca não é automaticamente duplicata descartada. |
| Incompletos/elegíveis | AbsorptionItem.status | Pending inclui dados incompletos ou revisão pendente. Ready/imported são elegíveis; não reconstrói elegibilidade histórica de busca/manual. |
| Incorporados | Lead.created_at | Novos IDs no período, não reencontros. |
| Início/conclusão | ResearchBatchItem + WorkAttempt | Primeiro início por item; usa menor início no ledger quando existe, pois started_at do item é sobrescrito em retomadas. Conclusão exige done e finished_at no período. |
| Falhas/interrupções | Item.status/error; WorkAttempt.status | Error/cancelled terminais separados de tentativas expired. Pending/paused continuam em estoque de fila. |
| Aprofundamento | Item.phase=deep | Fase alcançada entre itens iniciados no período, não prova de auditoria concluída. |
| Reuso | SmartSearch.skipped_recent | Contador de pesquisas recentes dispensadas em execuções encerradas; parcial e não convertido em chamadas hipotéticas evitadas. |
| Oportunidade/evidência insuficiente | CommercialReview.classification, dirty, refresh_at | Somente projeção canônica vigente: priority ou pending. Não roda Score nem atualiza índice durante leitura. Falta de índice é desconhecida, com cobertura explícita. |
| Revisão/seleção/adiamento/baixa prioridade | CommercialReview.state/decided_at | Última decisão humana no período. Unreviewed/reaberta não integra denominador de decisões atuais. |
| Rascunhos/aprovação | OutreachDraft.created_at/approved_at/status | Criação e aprovação separadas de autorização, contato e Outbox. |
| Próxima ação/vencimento | Lead.in_pipeline/stage/next_action/next_action_on | Ações atuais de negociações abertas; vencimento no dia local. Não recalcula o planejador de acompanhamento nem substitui suas recomendações. |
| Conclusões de tarefa | LeadActivity.metadata.action=followup_complete | Eventos explícitos; não infere conclusão por desaparecimento de tarefa. |
| Contato manual | LeadActivity email/whatsapp/call | Eventos legados sem event ou manual_activity, data occurred_at quando existente, senão created_at. Exclui not_reached/delivery_failure e espelhos outreach_accepted. Proveniência declarada. |
| Aceitação técnica | Outbox accepted + provider_id + conta própria + MessageEvent accepted | Uma mensagem por ID; recibos repetidos não duplicam contato. Menor timestamp de aceitação. Não comprova entrega/leitura. |
| Entrega/leitura | MessageEvent delivered/read | Somente evento explícito posterior à aceitação válida. Zero significa nenhum recibo conhecido, não que todas as mensagens falharam. |
| Resposta comercial associada | ReceivedMessage matched, conta/Lead/thread próprios + aceitação anterior | Classificações interest/information_request/objection/refusal/opt_out. Automáticas, insuficientes, falhas e associações ambíguas ficam separadas; mensagens sem Lead aparecem somente em all. |
| Resposta manual | LeadActivity reply manual/legado | Declaração do operador, fora da taxa de conversas rastreáveis. |
| Reunião/proposta | LeadActivity meeting/proposal manual/legado | Eventos declarados, não inferidos a partir de texto ou estágio. |
| Ganho/perda | Lead.stage + outcome_recorded_at | Estado atual com data explícita do desfecho. Encerramentos sem data ficam separados e não recebem timestamp inventado. |
| Consumo | ProviderOperation → WorkAttempt próprio | Operações do worker relacionadas a buscas/investigações rastreáveis; failed e reserved separados. Não equivale a requisições faturadas nem moeda. |

## Denominadores

- Elegibilidade: ready/imported / todos os itens de absorção recebidos no período. Estado atual dessa coorte.
- Duplicação explícita: ocorrências explicitamente duplicadas / ocorrências rastreáveis encontradas/recebidas no período. Não estima duplicatas desconhecidas.
- Conclusão: itens iniciados no período e concluídos até a consulta / itens iniciados no período. Uma conclusão de início antigo aparece no volume concluído, mas não nessa taxa.
- Seleção: selecionadas / empresas com última decisão humana no período. Inclui reviewed, selected, deferred, not_priority no denominador.
- Resposta: conversas `(Lead, conta, thread)` com resposta comercial posterior a uma aceitação técnica **no período** / conversas com aceitação técnica no período. Cada conversa conta uma vez; declarações manuais, mensagens automáticas e ambíguas não entram. Entrega é desconhecida e a coorte tem diferentes tempos de observação; não é conversão geral de prospecção.
- Médias de consumo: operações observadas no período atribuíveis à coorte / buscas iniciadas ou empresas com investigação iniciada no período. Não inclui operações posteriores ao instante da leitura nem atribui operações sem ledger.

Denominador zero resulta em null/“Sem base”, nunca em 0%. Contagens são descritivas; não há estimativa de qualidade comercial a partir de sucesso técnico.

## Tempo, custo e limites

Medianas: criação até atualização terminal de busca encerrada; criação do lote até primeira tentativa de investigação; duração de tentativas committed/failed com início/término; última decisão humana anterior ao rascunho; último contato anterior a uma atividade followup_set. Intervalos negativos e finais futuros são descartados. Tentativas expired não medem tempo ocupado. Nenhum desses intervalos mede esforço humano.

Tempo até disponibilidade para revisão, tempo de trabalho humano, chamadas hipotéticas evitadas por cache e custo monetário são indisponíveis. Não foi adicionado rastreamento de teclas/navegação nem reconstruído evento histórico. O orçamento exibido é o limite global configurado; consumo diário é apenas desta conta, por UTC. O saldo de outras contas não é exposto. Uma investigação com o erro canônico “Limite ou configuração indisponível” não permite distinguir orçamento de configuração: o diagnóstico mantém essa incerteza.

## Diagnósticos

Emitidos somente com quantidade positiva: itens pendentes sem coordenadas; duplicatas reconhecidas; fila pending em lote ativo/pausado; empresas sem decisão atual; rascunhos draft; destinatários sem e-mail/WhatsApp de formato válido; ações vencidas; desfechos sem data; busca source_limited; investigação encerrada por limite/configuração. Cada registro contém quantidade, população, período, consequência possível e link para a área existente. Não são atribuições causais nem autorizam contato. Formato válido não significa autorização ou ausência de opt-out.

## Comparações e histórico

Origem, estratégia geral/direcionada/absorção/manual, setor, país/cidade, mês de entrada: empresas incorporadas no período e estados atuais. Nível: empresas com itens iniciados no período, agrupados por modo/fase alcançada. Grupos se sobrepõem e no máximo 30 grupos por dimensão são retornados por volume, com total disponível. A cobertura de classificação acompanha cada grupo; n<30 é identificado como pequeno, sem declarar n≥30 representativo.

Os padrões de negociações encerradas foram movidos para agregação no servidor: não há requisição por empresa, nem lista de atividades enviada ao navegador. Datas ausentes não usam data de criação/último contato como substitutas. Snapshots ausentes não são recriados para o relatório. Comparações são descritivas, preservando o mínimo de seis desfechos, dois ganhos e duas perdas para prontidão. A avaliação supervisionada permanece em CommercialLearning/selection_quality, inclusive seus critérios próprios, abstenções, falsos positivos/negativos e limitações estatísticas. Nenhum peso do Score é alterado.

## Persistência, segurança e performance

Nenhuma tabela/migração nova: revisão 032 mantida. Consultas de projeções limitadas no backend, sem N+1; limite de 100.000 linhas por relação. Exceder o limite recusa o relatório inteiro com 422, sem taxa truncada. Os índices existentes por usuário/FK sustentam os testes locais; não se adicionaram índices sem evidência de necessidade.

A leitura usa snapshot de transação (SQLite SERIALIZABLE com BEGIN explícito; PostgreSQL REPEATABLE READ preparado, não homologado aqui), sem flush/commit de entidades. Todas as relações verificam proprietário; relações cruzadas inválidas não concedem acesso. Rate limit de 30 consultas/minuto por usuário. Autenticação e proteções existentes preservadas. Não há corpo de mensagem, destinatário, segredo ou lista de IDs no retorno. Texto de setor/cidade é renderizado pelo escape padrão do React. Não há HTML dinâmico, consulta NoSQL, upload, webhook ou nova integração neste módulo.

Não há cache de relatório. A ausência de índice comercial vigente é apresentada como cobertura parcial e pode ser resolvida usando a fila existente. Testes de 1.000/10.000 empresas registram consultas, tamanho da resposta e latência local; não são SLA de produção. PostgreSQL, instalação real, provedores e dispositivos físicos permanecem fora da homologação.
