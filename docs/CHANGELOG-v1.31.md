# Alterações — ScoutLIQ 1.31.0

Base: FULL 1.30.0, revisão 019. Migração aditiva: 020_applied_intelligence.

- Evidências com categoria, escopo, TTL por categoria, referência de pesquisa, última verificação, versão do analisador, traduções revisadas e reconciliação auditável. Falha de coleta não refuta observação anterior; contradição a retira de uso inclusive no limite de capacidade.
- Diagnóstico com observação concreta, cobertura por seis áreas e confiabilidade separada do Opportunity Score original. Próxima ação centralizada com comando executável e pré-condições.
- Abordagens determinísticas PT/EN/ES com estratégias e requisitos de histórico. Fatos livres sem tradução revisada bloqueiam idiomas estrangeiros. Conteúdo aprovado não equivale a permissão de envio.
- Política por destinatário exato/usuário/canal, bloqueio entre leads e invalidação de aprovações por alteração da política. Sem fusão por domínio/nome ou sufixo de telefone.
- Executor persistente sobre ResearchBatchItem e RadarSavedSearch existentes: claim atômico, lease, fencing, recuperação, tentativas limitadas, backoff, pausa/cancelamento, intervalo e orçamento diário.
- Navegador observa lotes/monitores; o modo padrão recusa execução via /step e escrita concorrente de resultados de monitores. Agendamento manual no servidor e legado explícito.
- Ficha editorial e progressiva; editor preserva mensagem ao trocar abas, avisa sobre saída com alterações e mantém edição em conflito/erro. Preview, comparação com versão salva e condição de contato separada.
- Correções reais de overflow mobile, contraste de contadores e acesso a resumos por teclado. Suíte histórica preservada com seletores semânticos e contrato de monitor atualizado.
- Sem mudanças nos motores scoring.py, research.py, providers.py ou automation.py, verificadas contra o ZIP base na validação dos pacotes.

Arquivos exatos alterados: release/CHANGED-FILES.json, também representados no PATCH-MANIFEST.json. Contratos e comparação detalhada: ARCHITECTURE-v1.31.md. Resultados: VALIDATION-v1.31.md.
