# ScoutLIQ 1.30.0 — evidências e aprovação operacional

- Ficha **Operação** no painel existente de oportunidade, com próxima ação contextual.
- Evidências persistidas com identificação, fonte, método, classificação, timestamp, validade e revisões na timeline existente.
- Captura idempotente dos checks de LeadResearch sem transformar ausência de sinal em afirmação de ausência. Nova pesquisa invalida snapshots anteriores.
- Rascunhos de e-mail/WhatsApp persistidos por oportunidade, editáveis e com preparação idempotente. Estruturas de mensagem PT/EN/ES; evidências mantêm o idioma original.
- Aprovação ligada ao conteúdo, destinatário, evidências e estado da oportunidade; expiração e revogação por edição. Nenhum envio real implementado.
- Preferência de não contato por oportunidade e pausa de rascunhos multicanal após resposta registrada.
- Histórico compartilhado com LeadActivity e exportação privada schema 13 preservado, com extensão opportunity_workflow_version 1. ORLIQ Bridge permanece schema 1; só a versão do produto muda.
- Migração aditiva 019; upgrade/downgrade testados em cópia isolada.
- Correção de sucesso indevido em JSON malformado; resultado de mutação sem confirmação fica explícito.
- Correção do build original (parâmetro não utilizado), overflow mobile de Negociações, navegação do cabeçalho em tablet e dependência transitiva source-map-js vulnerável.
- Na aba Operação, a próxima ação contextual substitui o rodapé de venda; as outras abas preservam o rodapé existente.
- Empacotamento e verificação corrigidos para a base real 1.29.0.

Preservados os motores de pesquisa, provedores, scoring e automações existentes. Não foram entregues worker em background, Gmail OAuth, WhatsApp Cloud API, recebimento automático de respostas, aprovação em lote ou redesign integral. Consulte AUDIT, INSTALL, SECURITY-GATE e VALIDATION da v1.30.
