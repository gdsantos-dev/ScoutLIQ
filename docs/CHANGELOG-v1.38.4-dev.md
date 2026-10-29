# Changelog — v1.38.4-dev

- Fila comercial integrada ao Radar, com classificação canônica, filtros, paginação, resumo verificável e seleção persistente entre páginas/filtros.
- Estados humanos separados do CRM; motivos, autor, data, histórico e reabertura persistentes.
- Sinalização de mudanças no contexto sem substituir decisões anteriores.
- Operações limitadas a 50 empresas, prévia persistente, confirmação explícita, resultados parciais, versões e idempotência.
- Preparação de vários `OutreachDraft` pelo serviço canônico, com destinatário e políticas revalidados; estratégia inicial quando faltam evidências confirmadas.
- Reutilização do editor existente para revisão individual, edição e aprovação de conteúdo.
- Novas investigações usam a fila e o worker existentes, sem execução de rede no fluxo de triagem.
- Migração 031 aditiva e proteção contra downgrade com decisões/recibos.
- Export existente inclui decisões e operações comerciais.
- FULL/PATCH e recibos internos/externos verificáveis.

Score, pesquisador, Absorção, investigação progressiva, CRM, comunicação, dispatch e autorização de envio permanecem preservados. Nenhum envio em lote, nova integração paga ou remake visual.
