# Changelog — v1.38.2-dev

- Importação CSV, tabelas e JSON tolerante por registro, com mapeamento assistido e limites seguros.
- Originais preservados; normalização reutilizável sem país/DDI inventados.
- Correção persistida, auditoria e concorrência por versão.
- Confirmação incremental de lotes parciais, sem recriar Leads.
- Deduplicação entre lotes e Radar, incluindo referências criadas pela Busca Unificada; filiais preservadas e possíveis duplicatas revisáveis.
- Recuperação de campos obrigatórios pelo worker existente: cache próprio, Geoapify opcional, reservas persistentes, timeout, retries, pausa, cancelamento e recuperação de lease.
- Sugestões geográficas com procedência; nenhuma coordenada de centro de cidade é aceita como estabelecimento.
- Dialog existente ampliado, com edição essencial visível e informações complementares recolhidas; suporte a 320 px, teclado e auditoria acessível.
- Migração aditiva 029. Reversão protege originais, correções e jobs.
- Score 3.0, investigação, comunicação, provedores e Busca Geral preservados.
- Fixture semântica histórica alinhada ao schema vigente; alteração limitada ao teste, sem mudança no motor.

Ver [validação](VALIDATION-v1.38.2-dev.md), [arquitetura](ABSORPTION-INTELLIGENT-v1.38.2-dev.md) e [instalação](INSTALL-v1.38.2-dev.md).
