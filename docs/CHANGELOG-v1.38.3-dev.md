# Changelog — v1.38.3-dev

- Investigação progressiva persistente em três níveis no worker existente, sem serviço pago de IA obrigatório.
- Preferências por usuário, desligadas por padrão, com entrada automática pela Busca e pela confirmação da Absorção.
- Solicitações manuais de até 100 empresas, divididas em lotes limitados; backlog, ordem persistente, recibo idempotente e deduplicação entre fluxos.
- Correção da perda silenciosa de IDs quando já havia um lote ativo no endpoint legado.
- Cache antes da rede, adequação e Score canônicos para limitar esforço, aprofundamento seletivo e preservação de resultados parciais.
- Projeção de prioridade operacional, confiança, cobertura, motivos e pendências, sem alterar os pesos do Score 3.0 nem o estágio de CRM.
- Teto diário de empresas e consultas por usuário; retomada por dia UTC; limites globais/provedores mantidos.
- Revogação de tokens em pausa/cancelamento, descarte de respostas obsoletas, controle de tentativas e encerramento de lotes sem itens após exclusão.
- Seleção múltipla, histórico de lotes e revisão dos resultados no Radar; ação de investigação na Absorção e controles nas Configurações existentes.
- Migração 030 aditiva sobre 029, com recusa de downgrade destrutivo. Testes históricos congelam o esquema da revisão que estão verificando.
- Recibos internos de fontes incluídos no FULL e no PATCH, com manifesto verificável; recibos externos identificam os ZIPs finais sem autorreferência.

Arquivos e hashes alterados constam do `PATCH-MANIFEST.json` dentro do PATCH. A relação legível está em `CHANGED-FILES-v1.38.3-dev.md`. Nenhuma migração histórica ou implementação de Score, adequação comercial, pesquisador de sites, evidências, provedores ou planejamento de descoberta foi reescrita.

Não houve deploy, campanha, envio de e-mail ou WhatsApp. A validação usa bancos descartáveis e provedores simulados.

## Correção encontrada na regressão

A revisão humana agora usa o formatador de data do produto, evitando sugerir uma data futura durante a diferença entre UTC e o calendário de São Paulo. Defeito já existente na base, reproduzido na regressão; teste de virada de data adicionado.
