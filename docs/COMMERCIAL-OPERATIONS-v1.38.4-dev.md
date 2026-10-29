# Operação comercial em lote — v1.38.4-dev

## Fluxo no Radar

Abra **Fila comercial** no Radar. A lista reúne empresas reais da Busca, Absorção, cadastro manual e CRM. A origem é preservada. A ordenação usa o Score 3.0 decrescente, com ID como desempate estável. Filtros de classificação, revisão, origem, empresa, cidade e setor são aplicados no backend.

A fila principal mostra empresas não revisadas ou com contexto alterado depois da decisão humana. Decisões anteriores podem ser consultadas por estado, com data e motivo. A reabertura cria um evento; não apaga a decisão anterior. A identidade do autor fica persistida no registro e vinculada ao usuário autenticado.

Selecione até 50 empresas. A seleção conserva IDs e versões durante filtros, páginas e recarregamentos da mesma aba; usa sessionStorage com a chave do usuário já utilizada no Radar. Não armazena conteúdos de rascunhos. Se a versão mudar, a prévia ou confirmação recusa aquele registro; selecione novamente após atualizar. “Selecionar página” também atualiza as versões dos registros visíveis já selecionados.

As ações são: revisar, selecionar para possível abordagem, adiar, marcar como não prioritária, reabrir, solicitar investigação e preparar rascunhos. Adiar e não priorizar exigem motivo. Nenhuma dessas ações muda o estágio do CRM, exclui a empresa, altera o Score ou concede autorização de contato.

Cada operação tem uma prévia persistente de 15 minutos, com elegibilidade e motivo individual dos bloqueios. A execução exige a confirmação explícita dos efeitos apresentados. O histórico “Operações recentes” permite retomar uma prévia ou consultar o resultado após perda de conexão.

## Resumo verificável

- Classe, Score e confiança vêm de `investigation.projection` e do Score canônico.
- Até três evidências atuais confirmadas aparecem na lista, com fonte e escopo; a contagem total permanece disponível.
- Sugestões de serviços são inferências identificadas, fundamentadas em evidências revisadas, não fatos sobre a intenção de compra.
- Conteúdo/descoberta podem sustentar Desenvolvimento Web; falhas técnicas revisadas podem sustentar manutenção e suporte.
- Sistemas/automações e ORLIQ Social só aparecem quando uma observação manual confirmada declara uma necessidade pertinente. Instagram público, sozinho, não gera recomendação de Social.
- Falta de evidência não produz diagnóstico técnico ou afirmação de ausência de site. Necessidade e contato podem permanecer pendentes sem reduzir artificialmente o Score.

O resumo é determinístico. Não utiliza IA paga, fontes externas ou consultas de rede ao abrir a fila. Para revisar evidências, conteúdo e aprovações, a interface abre o componente `OpportunityWorkflow` já existente.

## Persistência e concorrência

`commercial_reviews` contém estado humano, autor, data, motivo, versão e impressão do contexto revisto. Também guarda um índice descartável do Score/classificação canônicos. Esse índice não possui pesos próprios e nunca altera o Lead.

`commercial_operations` armazena chave idempotente por usuário, payload, prévia e resultados individuais. As referências de rascunhos continuam apontando para `OutreachDraft`; solicitações de investigação apontam para `ResearchBatch`. O histórico detalhado usa `LeadActivity`, inclusive estado anterior, ação e identificador da operação. O export existente inclui as decisões e os recibos das operações.

Mudanças ORM em Lead, LeadResearch, OpportunityEvidence e ResearchBatchItem invalidam o índice e incrementam uma geração. Trocar uma evidência por outra com a mesma contagem também invalida a decisão. Expiração de evidências é reconsiderada pelo índice. A decisão humana nunca é sobrescrita por essa atualização; a fila sinaliza reavaliação.

Confirmações são serializadas pelo lock do usuário e revalidam versões e contexto sob lock do Lead. Cada empresa usa um savepoint: conflitos conhecidos ficam como falha individual, enquanto registros válidos podem concluir. Erros inesperados de infraestrutura revertem a transação inteira e mantêm a prévia recuperável. Repetir uma operação concluída devolve o resultado persistido, sem duplicar efeitos.

O identificador do rascunho deriva da operação e do Lead. Uma nova operação explícita pode criar outro rascunho; repetir a mesma operação não cria. O limite canônico de 50 rascunhos por oportunidade é preservado.

## Preparação e comunicação

O endpoint individual e o lote chamam o mesmo serviço `create_draft`, extraído de `opportunity_workflow.prepare_draft` sem alterar suas regras. `compose`, `recipient_identity`, `recipient_blocker`, revisão e validade das evidências permanecem canônicos.

E-mail usa um endereço válido registrado no campo de contato; WhatsApp exige o campo WhatsApp válido. Um nome não vira e-mail, e um telefone genérico não vira uma conta WhatsApp. Contato recusado impede preparar o rascunho. Idiomas: PT-BR, EN-US e ES; observações livres em outro idioma exigem tradução revisada conforme o contrato existente.

A estratégia automática usa `verified_opportunity` apenas quando existem evidências atuais confirmadas que sustentam necessidade. Caso contrário, usa apresentação inicial sem alegações técnicas. Retomada e resposta exigem histórico correspondente. As mensagens continuam usando os templates atuais do compositor canônico; recomendações comerciais não autorizam inventar textos ou fatos específicos de um serviço.

Preparação não aprova conteúdo, não verifica consentimento e não autoriza envio. O código de comunicação, o bloqueio de dispatch e as autorizações individuais foram preservados integralmente. Não há envio em lote, adapter WhatsApp novo, campanha automática ou consulta a provedor nesta camada.

## Volume e consumo

Paginação padrão de 25 e máxima de 50, retornos compactos, agregação de contagens e consultas em lote para relações. Corpos de rascunhos e todas as evidências não são carregados para montar a lista. O detalhe completo só é consultado quando solicitado.

O índice é preenchido/atualizado localmente em blocos de até 250 empresas por chamada. Instalações antigas ou com muitas alterações mostram quantas avaliações ainda faltam; a interface continua a atualização automaticamente. Enquanto isso, a ordenação é válida para a parte já indexada. O cache tem janela máxima de cinco minutos para recomputar fatores temporais. Atualizações por SQL externo ao ORM não emitem o sinal imediato; são reconsideradas nessa janela. Na confirmação, o contexto é recalculado independentemente do cache.

O refresh de índice realiza escritas proporcionais ao bloco, com memória limitada; a leitura da página usa consultas agregadas sem N+1 de evidências/rascunhos. A busca por texto usa comparação escapada; não interpola SQL. Leituras da fila têm rate limit de 120/minuto; prévias e confirmações, 15/minuto por usuário. Investigações solicitadas continuam sob os limites e o worker da v1.38.3.

## Fronteiras

Validação local e sintética não comprova aumento de conversão, consentimento real nem conformidade de um destinatário. PostgreSQL, infraestrutura de produção, dispositivos físicos e provedores reais exigem homologação própria. Nenhum deploy, banco pessoal, cota real de pesquisa ou envio comercial é necessário para os testes deste ciclo.
