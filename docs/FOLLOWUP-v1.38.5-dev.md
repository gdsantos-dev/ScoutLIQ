# Acompanhamento comercial — v1.38.5-dev

## Uso

Em Gerir clientes → Negociações, abra **Acompanhamento comercial**. A mesma lista está disponível em Radar → Fila comercial → Acompanhamento. Não há outro CRM, pesquisador, worker ou mecanismo de comunicação.

1. Filtre atenção hoje, atrasados, respostas, execução pendente, aguardando retorno, bloqueados ou encerrados.
2. Veja a ação recomendada, motivo, data e Score canônico. Expanda o resumo para consultar origem, incertezas, ação manual e conteúdo de resposta associado.
3. Selecione até 50 empresas. Defina uma ação, adie, conclua a tarefa, solicite revisão, prepare rascunhos ou desative/retome acompanhamento.
4. Confira a prévia persistente: elegibilidade individual, bloqueios, ação anterior e efeito pretendido. Substituir ou concluir uma ação manual exige consentimento específico, além da confirmação da operação.
5. Rascunhos abrem no editor canônico. Preparar não aprova conteúdo, não verifica consentimento e não autoriza envio. A revisão continua individual.

O intervalo sugerido é configurável entre 1 e 90 dias, padrão 7, no fuso já registrado no usuário. A configuração não agenda envios e não habilita sincronização Gmail. Datas civis são calculadas com ZoneInfo; não são somas fixas de 24 horas em UTC.

## Fatos e recomendações

O planejador determinístico lê Lead, LeadActivity, OutreachDraft, ReceivedMessage, OutboxMessage, MessageEvent, RecipientPolicy e a projeção canônica da investigação. Não exige IA paga nem faz chamadas externas ao abrir a lista.

| Fato observado | Recomendação |
| --- | --- |
| Sem contato anterior | Preparar abordagem inicial ou confirmar investigação; nunca gerar follow-up por descoberta/seleção |
| Destinatário ausente/inválido | Verificar contato, preservando Score comercial |
| Rascunho sem aprovação | Revisar conteúdo |
| Rascunho aprovado | Revisar condição de contato; aprovação não é envio |
| Outbox queued/executing/uncertain | Acompanhar execução; nenhuma presunção de aceitação |
| Aceitação + recibo canônico | Aguardar retorno ou revisar follow-up após o intervalo |
| Aceitação sem recibo/data suficiente | Revisar registro incompleto; não derivar data de envio |
| Interesse/pedido de informações/objeção | Revisar resposta ou proposta; classificação continua sujeita a revisão humana |
| Resposta automática/ambígua | Aguardar humano ou revisar intenção; sem inferir interesse |
| Recusa, opt-out, falha de entrega ou bloqueio | Interromper novas sugestões de contato |
| Won/lost | Oportunidade encerrada, sem novas abordagens |

Aceitação técnica não confirma entrega ou leitura. O planejador reconhece um evento canônico de entrega quando existir; a integração Gmail atual não fornece tal confirmação. Ausência de resposta conhecida não significa que alguém ignorou a mensagem. Nenhum evento de entrega é criado por este ciclo.

ReceivedMessage só é usado com associação `matched` e outbox aceita do mesmo proprietário, conta, Lead e thread. O sincronizador mantém a verificação original de mensagem referenciada e destinatário; não passou a pesquisar a caixa indiscriminadamente. A única alteração em `communication_replies.py` impede substituir uma `next_action` já preenchida. A sugestão atual aparece na fila mesmo quando essa ação é preservada.

## Prioridade e decisões humanas

A ordenação operacional considera categoria de urgência, data, estágio, Score 3.0, confiança canônica e última atividade confiável, com ID como desempate estável. Uma resposta a revisar precede prospecção sem contato, mesmo com Score inferior. Bloqueados e encerrados não recebem prioridade de contato. Ação manual futura fica agendada; resposta nova pode continuar merecendo revisão prioritária.

`Lead.next_action` e `Lead.next_action_on` permanecem a fonte da próxima ação manual. Não são atualizados pela simples leitura do planejador. Definir ação segue o contrato existente de oportunidade ativa no Pipeline. Nenhuma operação altera estágio implicitamente.

Conclusão reconhece a sugestão/evento atual; um novo evento relevante pode voltar à fila. Pausa por data e desativação por empresa são preferências persistentes. Retomar acompanhamento não remove bloqueios nem modifica RecipientPolicy. Não há loop de reagendamento ou tarefa duplicada no worker.

## Registros manuais

No resumo da empresa, **Registrar atividade** permite e-mail, WhatsApp, ligação, reunião, proposta, resposta e nota. Campos: data local do ocorrido, resultado e observações. Tudo permanece em LeadActivity, com `provenance=operator_declared`, data/fuso e `provider_verified=false`; não há OutboxMessage ou MessageEvent fabricado.

A chave de requisição permite retomar uma gravação sem duplicá-la. Datas futuras são recusadas. O histórico mantém data de registro e data do ocorrido separadas. Contatos bloqueados não são liberados por atividade manual. Recusa/opt-out declarado em uma resposta suspende contato no Lead e pausa rascunhos pelo serviço existente; não altera a política do destinatário nem autoriza comunicação.

## Persistência, concorrência e recuperação

A migração 032, sobre 031, adiciona `followup_settings`, `followup_preferences` e colunas descartáveis de índice em `commercial_reviews`. Não duplica mensagens, tarefas, respostas ou Score. Preferências e operações entram no export existente.

Prévia e confirmação reutilizam CommercialOperation: limite 50, validade 15 minutos, idempotência por usuário, validação individual, versões do Lead/revisão/preferência e impressão do contexto. Alterações em mensagem, resposta, política, configuração, dia local ou dados invalidados exigem nova revisão. A confirmação utiliza também a trava curta de escrita canônica de comunicação, sem adquirir lease nem executar rede.

Conflitos conhecidos produzem resultado individual; erro inesperado reverte a transação inteira, permitindo repetir a confirmação. Preparação usa `create_draft`, `compose`, `recipient_identity` e `recipient_blocker` originais. A chave do rascunho deriva de usuário, Lead, evento, estratégia, canal, destinatário e idioma: outra operação não cria rascunho equivalente para o mesmo contexto.

## Consultas e limites

A lista tem páginas de 25, máximo 50, filtros SQL e índice local preenchido em blocos de até 250. A interface mostra pendentes e continua a indexação. Enquanto houver pendentes, a ordenação cobre apenas a parte indexada. O cache revalida em até cinco minutos e na virada do dia local; mudanças ORM invalidam imediatamente. Uma geração impede limpar a invalidação produzida por outra escrita durante o cálculo.

As relações são consultadas em lote: último rascunho, última outbox por estado, última resposta estritamente associada e até duas atividades por tipo. A janela de atividades é conservadora: um registro antigo fora dela pode exigir revisão do histórico, em vez de inferir contato. Não são carregados todos os corpos de mensagens e rascunhos para renderizar a lista.

Este ciclo não homologa PostgreSQL de produção, dispositivos físicos, provedores reais, consentimento real ou conversão comercial. Templates de resposta/follow-up continuam sendo os do compositor determinístico existente; personalização detalhada das respostas exige revisão humana no editor.
