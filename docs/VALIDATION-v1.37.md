# Validação — ScoutLIQ v1.37.0

Data: 22/10/2026. Base exclusiva FULL v1.36.0, SHA256 `64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75`. A instalação pessoal e a baseline v1.20 não foram modificadas. Testes utilizam bancos separados, identidades sintéticas e fixtures declaradas.

## Resultados

| Verificação | Resultado | Evidência |
|---|---|---|
| Backend completo | **332 passaram** | evidence-v137/backend-release-closed.xml |
| Revisão/catálogo após ajuste final de limite | **42 passaram** (subconjunto, não somar) | evidence-v137/backend-review-final.xml |
| Migração 027 e catálogo | **4 passaram** (subconjunto) | evidence-v137/backend-location-final.xml |
| Frontend unitário | **23 passaram**, 7 arquivos | evidence-v137/frontend-unit-release.xml |
| TypeScript aplicativo/E2E e build | Aprovados, dependências limpas pelo lockfile | Scripts npm build/typecheck:e2e |
| E2E distintos | **53 passaram** | evidence-v137/browser-group-a.json e browser-group-b.json; logs por suíte |
| Score 3.0 vs base exata | **175 casos com resultado completo idêntico** | evidence-v137/score-baseline-v137.json |
| Auditoria frontend/backend | **0 vulnerabilidades conhecidas** | npm-audit-final.json e pip-audit-v137.json |
| Literais de tradução reconhecidos | 1064 ocorrências, nenhuma lacuna detectada pelo critério estático | i18n-static-audit.json |
| CSS por superfície | 44 módulos, ordem/conteúdo preservados na extração | css-surface-equivalence.json |
| FULL/PATCH | Manifestos, aplicação, backup, conflito, reaplicação e reversão conferidos em cópia descartável | evidence-v137/package-checks.json; relatório com hashes em release/VALIDATION.json no workspace |

As 332 verificações de backend incluem as 265 da base e novas coberturas. Os 53 E2E preservam os 43 casos da base e acrescentam dez cenários de busca/mapa. Seletores dos fluxos substituídos foram adaptados sem remover garantias de negócio. Não somar reruns e subconjuntos para inflar a contagem.

### Distribuição E2E

Redesign 25; workflow 5; learning 2; experience 3; unified-search 9; smart-search 3; map-search 1; autonomy 2; intelligence 2; communication 1. O runner cria um servidor/banco por suíte para respeitar os limites reais de login e lançamentos. Não houve relaxamento de rate limiting para fazer testes passar.

## O que foi exercitado

- Auth, sessão, autorização, CSRF, propriedade, mass assignment, isolamento e versões concorrentes.
- Pedido simples, dúvidas materiais, aliases de setor, alvo padrão/opções, ajustes opcionais, política semântica e fallback sob reserva.
- Catálogo e seleção por ID, homônimos, ausência de cobertura, geometria inválida, mapa e recorte sem localização inventada.
- Consultas históricas com filtros e geometria preservados, idempotência, snapshot, monitor, cancelamento em trânsito e lease expirado.
- Cache isolado, quotas persistentes, concorrência de reservas e consumo mantido após falhas.
- Worker com navegador fechado, persistência/reload, rotinas, score, evidências, CRM, aprendizado e comunicação simulada sem rede externa.
- Confirmação comercial explícita sem mudança de fatos; divergências exigem justificativa. Campos desconhecidos não viram fatos confirmados.
- Desktop/mobile, foco/Escape, rolagem, nesting, estado offline/erro/retry, idioma, navegação, reduced-motion e axe.
- Migração 026↔027 preservando tabelas anteriores, integridade e FKs. Migrações históricas permanecem inalteradas.

## Correções durante a validação

A suíte detectou codificação indevida em rótulos do adaptador extraído; corrigida antes da rodada completa de 332 aprovações. Três cenários E2E ainda esperavam controles antigos; foram migrados para os controles e o worker compartilhados, preservando CRUD/monitoramento/isolamento. A compilação detectou referência relativa de tokens após separar CSS; corrigida e validada pelo build e pela regressão visual. A auditoria encontrou três alertas nas dependências de desenvolvimento; atualizações compatíveis do lockfile deixaram a auditoria final sem alertas.

## Avisos não ocultados

Duas deprecações no ambiente Python de testes (Starlette/httpx e alias AnyIO). Vitest 4.1.12 no Windows/Node 24 concluiu 23 testes com código de sucesso, mas informou 44 FILEHANDLEs e timeout de 10 s no encerramento do runner; não foi observada falha na aplicação ou nas asserções. Vite informa chunk grande de MapLibre, carregado sob demanda. Esses avisos não são homologação de outros ambientes nem foram convertidos em testes ignorados.

## Estados da entrega

**Implementado e testado localmente:** escopo funcional descrito no changelog, migração, segurança proporcional, UX, compatibilidade e artefatos. **Homologado externamente nesta execução:** nenhum provedor ou ambiente de produção. **Parcial por capacidade:** cobertura internacional/fontes, cenários e conteúdo dinâmico fora dos catálogos de idioma. **Bloqueado por insumos externos:** credenciais/autorização para homologação real e envios. Detalhes em EXTERNAL-LIMITS-v1.37.md.

Fixtures comprovam contratos e funcionamento. Não comprovam veracidade comercial, precisão de seleção em campo, conversão, tarifas reais ou autorização para contato. Nenhum deploy nem envio comercial real foi realizado.
