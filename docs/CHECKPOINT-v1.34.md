# Checkpoint verificável — Prompt 2/3

Data: 17/10/2026. Diretório de trabalho: `work/v1.34.0/ScoutLIQ`. Base extraída exclusivamente do ZIP FULL v1.33.0, hash `f4915a73ffc2231e092ae9397c23c7bcd42f44213fb5567ca1d97c4be3d6b03e`. Não retomar do código pessoal na raiz nem de versões antigas. Conferir o manifesto do FULL desta entrega e SHA256SUMS antes de continuar.

## Estado objetivo

| Frente | Estado | Limite |
|---|---|---|
| P0.1 | Preservada; regressão local | Supervisor, rotinas, orçamento, ledger, recuperação e 022 não reconstruídos |
| P0.2 interpretação | Implementada e testada com respostas controladas | Modelo real, preço, disponibilidade e qualidade semântica externa não homologados |
| P0.2 descoberta | Plano adaptativo integrado no worker existente | Heurística baseada em seleção técnica; sem medida causal de ganho comercial |
| P0.2 contatos/site | Implementado no HTML já investigado e na ficha | Sem redes sociais autenticadas, inferência de pessoas, consentimento ou confirmação de caixa postal |
| P0.2 avaliação | Sete casos sintéticos; baseline preservado | Zero casos humanos revisados e zero resultados comerciais |
| P0.3 | Pendente como fatia funcional | Há helper de métricas; ainda não há importação/versionamento de casos humanos nem calibração versionada |
| P0.4 | Pendente | OutreachDraft/RecipientPolicy/LeadActivity e aprovações anteriores preservados; outbox, OAuth Gmail e sincronização ainda não implementados |
| Prompt 3 | Não iniciado | Não iniciar redesign ao retomar |

## Próximo trabalho: P0.3 completo

1. Criar migração 024 aditiva para casos revisados, revisões de rótulo e versões de critérios, todos com user_id, IDs externos de importação/idempotência e versão otimista. Referenciar Lead/OpportunityEvidence/LeadActivity existentes quando houver; não criar outro cadastro de empresas.
2. Schema de importação deve guardar origem manual ORLIQ, identidade desambiguada, data/revisor, decisão humana, justificativa, evidências e resultado comercial (incluindo desconhecido). Proibir mass assignment, rótulo inferido como humano, referência a recurso de outra conta e sobrescrita silenciosa. Importar arquivo/JSON com prévia, limites e commit transacional.
3. Reutilizar `backend/selection_quality.py` para FP/FN/precisão/recall/ranking de casos elegíveis e independentes. Distinguir treino/validação, abstensão, falta de rótulo, amostra pequena e desfecho desconhecido. Comparar os mesmos casos e snapshots entre critérios. Não confundir os sete fixtures de `scripts/evaluate_commercial_quality.py` com revisão humana.
4. Sugestões de recalibração precisam trazer casos de suporte, tamanho da amostra e efeito comparado. Nada altera automaticamente `backend/scoring.py`. Versão proposta, aprovação explícita, aplicação e reversão devem registrar antes/depois e permitir comparar baseline. A existência do modelo semântico não muda os pesos.
5. UX mínima dentro da revisão comercial/ficha e configurações existentes; sem novo painel paralelo. Validar permissões cruzadas, persistência, duplicação/reimportação, correção e reversão; depois suíte completa e E2E.

## Em seguida: P0.4 completo

1. Uma outbox persistente compartilhada com key de idempotência, conteúdo/aprovação congelados, estados de envio incerto e auditoria LeadActivity. Revalidar política, identidade, autorização, validade e bloqueios imediatamente antes do envio. Uma aprovação antiga não autoriza envio real.
2. Adapter Gmail oficial, OAuth state de uso único e vinculado à conta, escopos mínimos compatíveis com envio e leitura de respostas, armazenamento cifrado de refresh tokens, rotação/revogação/reconexão. Não usar credenciais da sessão de QA ou connector pessoal para a aplicação.
3. Leases/fence e retry pelo worker existente. Timeout após possível envio deve ficar incerto, reconciliado com identificador estável antes de reenviar. Não há exatamente-uma-vez garantido por um POST remoto sem suporte do provedor.
4. Sincronização de replies com cursor persistente, dedup por mensagem/conta, associação por thread/headers/participantes verificados, nunca só assunto ou nome. Resposta atualiza LeadActivity, contexto e próxima ação; opt-out bloqueia o destinatário. Sanitizar conteúdo remoto e não executar instruções contidas nas mensagens.
5. Contrato de canal para WhatsApp Cloud API reutilizando outbox/política/auditoria; webhooks com assinatura, opt-in e condições do canal. Não duplicar o motor. Homologação precisa de conta/credenciais oficiais e destinatários de teste autorizados.

## Bloqueios externos versus pendências técnicas

P0.3/P0.4 são trabalho técnico restante, não bloqueio por falta de credenciais. Implementação e testes controlados podem avançar sem segredos reais. Homologação de OpenAI/Gmail/WhatsApp, qualidade em prospecção real, faturamento, produção/Railway/HTTPS e dispositivos físicos permanecem não realizados. Envio comercial real exige condições verificadas e autorização humana explícita específica; nenhuma foi concedida nesta execução.

Leia também CHANGELOG, INTELLIGENCE, SECURITY-GATE e VALIDATION v1.34. O banco pessoal permanece intocado. Não apagar ou recriar os mecanismos P0.1. Não interpretar este checkpoint como missão integral concluída.
