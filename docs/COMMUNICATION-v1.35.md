# Comunicação operacional — v1.35

O núcleo compartilha OutreachDraft, RecipientPolicy, LeadActivity, ResearchExecutor, WorkAttempt e ProviderOperation. As tabelas 026 armazenam conexões, revisão da condição de contato, execução, eventos e deduplicação de respostas. Não existe outro CRM, scheduler ou score. A integração é **implementada e testável com provedor controlado**; homologação Gmail real não foi realizada.

## Fluxo de operação

1. Configurar o servidor conforme GMAIL-v1.35.md. Conectar uma conta em **Integrações → Gmail**. O usuário precisa estar autenticado no ScoutLIQ.
2. Na ficha **Operação**, registrar a condição exata do destinatário e sua referência. Esta versão permite envio somente para permissão explícita ou solicitação recebida. Relacionamento existente ou endereço público isolado não habilitam envio.
3. Preparar/editar o OutreachDraft. Manter identificação e orientação de remoção no texto; aprovar o conteúdo e suas evidências.
4. Em **Envio e acompanhamento**, registrar origem, evidência da permissão, revisão da jurisdição e regras do provedor. O país do Lead deve coincidir com o da política e estar habilitado no servidor. A revisão é uma declaração auditável do operador, não certificação jurídica automatizada.
5. Selecionar a conta, registrar a legitimidade do remetente e a revisão SPF/DKIM/DMARC, conferir opção de remoção e autorizar explicitamente esta execução. A fila só é criada após essa ação. Por padrão a autorização dura até 24h; API permite 1–72h, sempre limitada pela validade de conteúdo e condição. Agendamento deve caber nesse prazo.
6. O worker já existente verifica novamente todos os vínculos, versões, conta, usuário ativo, limites, supressão e prazo. Aceitação técnica fica no histórico da mesma oportunidade. Nenhuma resposta produz envio automático.

Os endpoints antigos de aprovação continuam sendo aprovação de conteúdo. O endpoint antigo `dispatch` permanece fechado e orienta a autorização explícita na outbox; não foi reinterpretado como permissão de envio.

## Estados e garantias

| Estado | Registro responsável | Significado / próximo passo |
|---|---|---|
| Rascunho / aguardando aprovação | OutreachDraft `draft` | Texto editável, sem autorização operacional. |
| Aprovado | OutreachDraft `approved` | Conteúdo aprovado; ainda não permite rede. |
| Bloqueado | Outbox `blocked` | Guarda de autorização/contato falhou antes da tentativa. Revisar os motivos. |
| Agendado | `scheduled` | Data futura ou limite/intervalo de envio. A validade continua correndo. |
| Na fila | `queued` | Autorização persistida, ainda sem tentativa de envio. |
| Em execução | `executing` | Lease exclusivo do ResearchExecutor; pode estar antes ou depois da fronteira de rede. |
| Aceito pelo provedor | `accepted` | ID de mensagem/thread confirmado pela API ou reconciliação exata. **Não é entrega ou leitura.** |
| Resultado incerto | `uncertain` | Tentativa começou e não há recibo inequívoco. Nunca entra novamente em envio automático. |
| Falhou | `failed` | Recusa explícita ou falha conhecida antes da rede. Sem retry de envio automático. |
| Cancelado | `cancelled` | Interrompido antes de começar a tentativa de envio. |

Depois da fronteira persistida `wire_started_at`, cancelar registra intenção de cancelamento, mas não desfaz uma aceitação externa. Interrupção após essa fronteira vira incerteza. Recuperação antes da fronteira permite retomar com todas as guardas reavaliadas. Atualizações locais após o início não podem impedir uma operação de rede já iniciada; esse é o limite explícito de cancelamento.

Cada item possui request UUID, hash da entrada, unicidade da revisão do rascunho, snapshot completo do conteúdo e autorização vinculada a operador, conta/versão, canal, destinatário, aprovação/evidências, Lead, política e revisão de contato. Cliques repetidos retornam o mesmo item; reutilizar a chave para outro conteúdo causa 409. Um rascunho com execução incerta/em andamento/aceita não pode ser reenfileirado, mesmo com nova revisão.

Um Message-ID fixo por item permite consultar mensagens enviadas. A reconciliação exige um único resultado com Message-ID, remetente/destinatário exatos e rótulo SENT. Zero resultados **não prova ausência de envio**. Há até três consultas automáticas e dez no total; uma ação manual solicita nova consulta dentro do backoff. Nunca há retry automático de `messages.send`. Não há garantia de exatamente uma vez: para nova mensagem, o operador precisa resolver a incerteza no provedor e tomar uma nova decisão comercial.

Limites: máximo 100 pendências por usuário; até 100 tentativas de envio/dia por usuário, configurável para menos e padrão zero; intervalo mínimo de 60s; orçamento de tarefas/HTTP/provedor da infraestrutura existente. Reservas de rede são persistidas antes de HTTP. OAuth interativo tem rate limit próprio; não pertence ao orçamento do worker. Quantidades de operações não representam custo monetário ou cota faturável Google.

## Respostas

O acompanhamento é opt-in por conta, na tela Integrações. Cursor Gmail, página pendente e IDs restantes são persistentes. Cada passagem lê até oito mensagens conhecidas; cursor final só avança junto do commit das mensagens/eventos. Chave conta+message ID impede duplicações. Falhas preservam cursor; três falhas pausam sincronização até revisão.

A associação exige conta do usuário, thread de uma mensagem aceita, References/In-Reply-To com Message-ID conhecido, remetente exato e destinatário incluindo a conta autorizada; CC ou cabeçalhos críticos duplicados tornam a associação conservadora. Nome, domínio e assunto nunca bastam. Ambiguidade não é resolvida por adivinhação: somente IDs/status são registrados, sem conteúdo no CRM. Associação identifica a conversa; não é certificação criptográfica da pessoa que escreveu.

Importa até 4.000 caracteres de texto, sem anexos, HTML ativo, tracking ou histórico citado. HTML é convertido em texto e a UI escapa o resultado. Regras conservadoras distinguem interesse, pedido de informação, objeção, recusa, opt-out, autoresposta, falha de entrega e insuficiente. Nenhum conteúdo recebido vira instrução ou chamada de ferramenta. Resposta comercial atualiza LeadActivity e a próxima ação; mensagens antigas não substituem a ação da mais recente. Recusas/opt-out suprimem o destinatário e interrompem pendências; nenhuma nova mensagem é enviada automaticamente. Bounces sem associação exata ficam sem vínculo; não se inventa confirmação de entrega nem de falha de uma oportunidade.

Histórico expirado (404): ressincroniza somente threads conhecidas, até 500 threads e as últimas 100 mensagens de cada uma, em grupos de três. Limites ou respostas >2MB implicam cobertura parcial/interrupção, preservada no estado. Não é sincronização de toda a caixa nem garantia de recuperar todo histórico antigo. Novas alterações posteriores ao cursor de reinício são lidas incrementalmente.

## WhatsApp

`channel_contract.py` documenta capacidades e a fronteira compartilhada de envio/reconciliação. Os estados, identidade exata, aprovações, supressão, outbox e histórico são reutilizáveis. **Adapter Cloud API não implementado**, sem template aprovado, janela presumida, webhook público ou automação WhatsApp Web. A futura fatia deve validar opt-in, template/idioma, janela real, assinatura e dedup de webhook, custos e identificação do número empresarial antes de registrar um adapter executável. Esse P1 é parcial, não integração concluída.

## Limites desta entrega

- Diagnóstico DNS automático SPF/DKIM/DMARC: não implementado; há revisão manual documentada, exibida como tal. Não inferir aprovação de reputação/deliverability.
- Gmail real, PKCE do cliente específico, quotas reais, verificação OAuth e publicação externa: pendentes de homologação.
- Política automática de legalidade internacional não é implementada. Há bloqueio padrão, países explicitamente habilitados e revisão de evidências pelo responsável. Consulte orientação aplicável antes de habilitar mercados.
- Apenas a identidade primária retornada por getProfile; aliases, delegação e caixas compartilhadas não são habilitados.
- Não há campanha de disparo em massa, envio de anexos ou modelo de IA sobre emails.
