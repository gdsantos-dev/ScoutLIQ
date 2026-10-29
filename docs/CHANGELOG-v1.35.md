# v1.35.0 — Commercial Learning & Outreach Execution

Base exclusiva FULL 1.34.0, Prompt 2/3. Preservados supervisor, pesquisa/descoberta, rotinas, ledger, CRM e identidade. Prompt 3 não iniciado.

## Aprendizado supervisionado

Importação JSON com prévia persistente, validação por registro, deduplicação de identidade, idempotência, atestado humano, controle de versões e commit transacional. Casos vinculados ao Lead ou externos identificados; revisão/evidências/resultados/histórico separados. Exportação dos registros revisados e avaliações.

Métricas de TP/FP/FN/TN, precisão/recall, cobertura, abstenção, P@K/NDCG e recortes por região/setor; avisos de amostra insuficiente. Snapshots congelados de desenvolvimento e validação. Sugestões e propostas de calibração sem aplicação automática; comparação de regressões, aprovação específica e rollback auditável. Score 3.0 permanece o único motor.

UX integrada à ficha Operação e ao Histórico existente, sem novo painel ou redesign. Migrações 024/025.

## Comunicação

Outbox persistente vinculada a OutreachDraft e RecipientPolicy, snapshots de autorização, contas por usuário, idempotência, orçamento diário, agendamento, cancelamento, lease e recuperação no worker existente. Resultado incerto separado da falha; reconciliação sem reenvio automático. Aceitação técnica não é entrega/leitura.

Gmail oficial: Authorization Code, state de uso único vinculado à sessão, PKCE S256, redirect fixo, tokens cifrados com biblioteca fixada, escopos send/readonly, refresh, desconexão/revogação e reconexão que invalida autorizações antigas. Sem acesso implícito ao Gmail do ChatGPT.

Cursor persistente de respostas, dedup por conta+mensagem, associação por thread/referências/participantes, minimização de conteúdo e classificação conservadora. Próxima ação e histórico no Lead; recusa/opt-out interrompem follow-ups. Gmail em Integrações e execução na ficha existente. Migração 026.

## Limites declarados

Nenhuma homologação Gmail real nem envio comercial executado. Não há evidência de melhoria comercial real sem casos ORLIQ representativos. WhatsApp tem contrato compartilhado, sem adapter executável. DNS/entregabilidade e jurisdição exigem revisão documentada pelo operador; diagnóstico DNS automático não foi implementado. Histórico Gmail antigo tem recuperação limitada, identificada como parcial quando ultrapassa limites. Detalhes e estados em VALIDATION-v1.35.md e COMMUNICATION-v1.35.md.
