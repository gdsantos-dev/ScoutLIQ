# Investigação autônoma e qualificação progressiva — v1.38.3-dev

## Base e arquitetura

Base integrada v1.38.2-dev conferida contra os 527 arquivos do manifesto, sem alterações locais divergentes. FULL de origem: SHA256 `39fb92f3f4bf87c35cfea5a244001107e923bdaa568e3fa4e96d3726c35e0cd2`. Busca Geral, Absorção Inteligente e migração 029 preservadas.

`backend/investigation.py` aplica política determinística aos modelos existentes `ResearchBatch` e `ResearchBatchItem`. O executor continua sendo `research_worker.py`, com o mesmo lease global, token, `WorkAttempt`, `ProviderOperation`, recuperação e cotas. Nenhum executor adicional, serviço de IA pago ou motor de comunicação foi criado.

A migração aditiva 030 acrescenta preferências JSON ao usuário; configuração congelada, identificador de solicitação e ordinal ao lote; fase, decisão e data de débito à tarefa. Não altera tabelas comerciais, pesos do Score ou migrações anteriores. O upgrade foi projetado com tipos e operações SQLAlchemy/Alembic compatíveis com SQLite e PostgreSQL. A homologação de concorrência em PostgreSQL real permanece externa.

## Entrada e persistência

- Automação de Busca e Absorção começa desabilitada. Cada fonte pode ser habilitada separadamente em Configurações. Salvar preferências não dispara uma varredura retroativa.
- Busca enfileira somente empresas recém-criadas. Absorção enfileira somente itens efetivamente confirmados. Cadastro e enfileiramento compartilham a transação.
- Seleção manual no Radar admite até 100 IDs próprios. Sem seleção, “Investigar melhores” usa até 100 resultados filtrados, na ordem atual. Na Absorção, a ação de investigação reutiliza os Leads importados do lote aberto; pendências já enfileiradas são reconhecidas.
- Solicitações são divididas em lotes de até 25 empresas, limitados pela preferência “Empresas por lote”. Ordinais persistentes mantêm a ordem de entrada por usuário. A mesma empresa pendente, em execução ou pausada não ganha outra investigação pendente; a nova solicitação registra `already_pending`.
- UUID de solicitação é idempotente por usuário, inclusive depois de concluído. Reutilizar o UUID com outro conjunto de empresas retorna 409. Identificadores de outro usuário retornam 404.
- A restrição antiga que devolvia um lote ativo e ignorava os novos IDs foi removida também do endpoint legado. Os limites contratuais de 25 IDs dos modos web/deep permanecem; a nova entrada progressiva admite 100.
- A Busca Inteligente reconhece empresas já pendentes em outro lote e não cria pesquisas duplicadas. Quando a automação progressiva está habilitada, parte da investigação pode terminar depois da execução da Busca; os resultados atualizados são revisados na fila do Radar. A conclusão da descoberta não implica conclusão da qualificação.

## Política `progressive-1`

1. **Conferência econômica:** verifica identidade, cidade, categoria, adequação e Score canônicos. Demonstração, incompatibilidade ou identidade insuficiente encerram o esforço sem rede. Uma avaliação recente sem necessidade relevante também evita novas consultas. Pesquisa recente é reutilizada; falha de acesso não é tratada como cache conclusivo.
2. **Pesquisa web:** reutiliza `WebsiteResearcher.research`, seu limite de candidatos, timeout, fontes e proteção de destino público. Os resultados passam por `_persist_research_result`, sinais comerciais, evidências e contexto existentes. “Não encontrado” não comprova ausência de site.
3. **Aprofundamento:** só é agendado com site confirmado, adequação compatível, necessidade ainda desconhecida ou relevante segundo o Score, e canal público, Instagram ou volume mínimo de avaliações. Preferência de aprofundamento e auditoria recente também são respeitadas. Reutiliza `deep_audit`; nenhuma URL é buscada por um novo cliente HTTP.

Cada fase é um claim independente. A etapa web fica salva antes de iniciar auditoria. Uma falha na auditoria preserva seus resultados anteriores e os demais Leads. Uma empresa sem site confirmado pode continuar promissora, sem auditoria técnica aplicável.

O Score 3.0 não foi modificado. A projeção operacional utiliza seu valor, cobertura, confiança, dimensões e adequação; não soma pontos e não substitui o estágio de CRM:

| Classe | Critério principal |
|---|---|
| Prioritária | Score canônico qualificado; revisão comercial humana indicada |
| Promissora | Adequação compatível e sinais públicos disponíveis, com lacunas |
| Pendente | Identidade/categoria/localização ou evidências insuficientes |
| Baixa prioridade | Incompatibilidade ou avaliação canônica suficiente sem necessidade relevante |
| Investigação indisponível | Erro técnico ou limite impediu concluir a tarefa |

Falha técnica tem precedência na apresentação da tarefa; não redefine o potencial comercial do cadastro. Motivos, fase, pendências, Score e confiança são apresentados junto ao resultado. Decisões relevantes ficam no `LeadActivity`, com lote e versão dos critérios. Observações geradas continuam sujeitas às regras de revisão e proveniência do sistema de evidências. Pesquisa concluída não significa venda provável nem autorização de contato.

## Budgets e controle

| Controle | Padrão | Faixa |
|---|---:|---:|
| Empresas por lote | 20 | 1–25 |
| Investigações por dia/usuário | 40 | 1–100 |
| Operações de rede por lote | 100 | 1–400 |
| Operações de rede por dia/usuário | 150 | 1–500 |
| Freshness | 30 dias | 1–90 dias |

O débito de investigação ocorre uma vez por item por dia UTC. Uma continuação no dia seguinte ocupa uma vaga nesse dia; as fases do mesmo dia não duplicam a vaga. Fases e retentativas continuam consumindo o orçamento global de tarefas; portanto, esse orçamento pode ser mais restritivo que o número de empresas. Operação de rede representa chamada de adaptador, não unidade monetária nem requisição HTTP individual de redirecionamento. Os limites globais e por provedor já existentes continuam valendo.

O teto diário usa UTC. Quando falta saldo diário por usuário, a fila aguarda o próximo dia, sem perder a etapa salva. O orçamento HTTP diário considera operações do usuário registradas no ledger compartilhado. Uma redução de preferência passa a restringir lotes antigos; os limites congelados de um lote não são ampliados por uma edição posterior.

Até três tentativas por fase; falhas temporárias usam backoff de 30/60/120 segundos. Exaustão diária durante uma chamada aguarda o próximo dia dentro desse limite de tentativas. Configuração inválida, orçamento total do lote ou limite global/provedor encontrado durante a chamada encerram com pendência explícita e resultado parcial preservado. Reavaliação manual cria nova solicitação, respeitando cache e cotas. Timeout, número de candidatos e páginas continuam limitados pelo pesquisador existente.

Pausa/cancelamento revogam tokens de tarefas em voo. Pausar e retomar imediatamente não revalida a resposta antiga. Resultados com lease expirado ou versão de Lead/pesquisa alterada são descartados. Cancelar não apaga resultados já confirmados. Lotes vazios após exclusão de Lead são encerrados. Desabilitar uma fonte impede novas entradas; lotes já existentes permanecem controláveis no Radar.

## Segurança e fronteiras

Rotas usam a autenticação, CSRF, limite de corpo e rate limiting existentes. DTOs fechados impedem campos extras e alteração de proprietário. IDs e consultas são filtrados por usuário. O lock transacional de usuário serializa deduplicação; o executor global serializa claims e reservas. URLs públicas passam pela validação SSRF do pesquisador, incluindo resolução de endereços e redirecionamentos. Texto externo não é executado como código e a interface usa renderização React escapada.

Novos registros operacionais não incluem credenciais ou respostas de exceção do provedor. Mensagens de erro são controladas. Não foram criadas rotas administrativas, uploads executáveis, bancos NoSQL, pagamentos ou webhooks. Controles dessas áreas existentes permanecem intactos. Nenhum envio de e-mail/WhatsApp, rascunho ou campanha é produzido pela investigação.

Não houve deploy, uso de banco pessoal ou homologação de provedores reais. Credenciais, políticas dos provedores, quotas reais, HTTPS, infraestrutura de produção e PostgreSQL precisam de validação no ambiente de destino. Casos sintéticos comprovam contratos técnicos; não comprovam ganho de conversão comercial da ORLIQ.
