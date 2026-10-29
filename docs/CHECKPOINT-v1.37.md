# ScoutLIQ v1.37.0 — checkpoint final

Concluído em 22/10/2026. Escopo local da v1.37 implementado e validado. Versão promovida a 1.37.0 nos metadados da aplicação e do pacote. Não houve deploy ou envio comercial real.

## Base e invariantes

Base exclusiva: work/v1.36.0/ScoutLIQ/release/ScoutLIQ-v1.36.0-full-source.zip.
SHA256: `64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75`.
Manifesto da base conferido. Baseline v1.20 e instalação pessoal preservadas.
Score, CommercialFit, outreach e revisões históricas de migração permanecem iguais à base. As dez adaptações de arquivos backend/env necessárias estão fixadas por hash em REVIEWED-ENGINE-CHANGES-v1.37.json; o checkpoint recusa alterações adicionais não revisadas. Novos módulos e a migração 027 aparecem no manifesto completo.

## Escopo encerrado

P0.1 contratos/consolidação; P0.2 geografia validada; P0.3 busca/worker compartilhados; P0.4 simplificação/revisão contextual; P0.5 diálogos; P0.6 refinamento fundamentado nas referências; P1.1 idiomas afetados; P1.2 CSS por superfície; P1.3 validação local e distribuição.

Consultas históricas não são reescritas como texto. Monitores usam o SmartSearch existente sem acrescentar investigação não autorizada. A API síncrona antiga preserva sua resposta por adaptador comum. Nenhum score, scheduler, CRM ou motor de comunicação paralelo foi criado.

## Evidências

332 backend, 23 unitários frontend, 53 E2E distintos, 175 comparações completas de Score com a base; subconjuntos adicionais documentados sem somar contagens. Migração 026↔027, quotas concorrentes, cancelamento, isolamento, mobile/desktop, idiomas e fluxo de revisão exercitados. Dependências reproduzidas com npm ci; auditorias atuais sem vulnerabilidades conhecidas. Ver VALIDATION-v1.37.md para avisos e limites.

FULL e PATCH exato estão no diretório release do workspace, acompanhados de SHA256SUMS.txt, CHANGED-FILES.json e VALIDATION.json. O FULL contém fontes, migrações, documentação e evidências selecionadas; runtime, dados pessoais e credenciais reais estão excluídos. O PATCH valida hashes antes de escrever e preserva configuração/banco.

## Retomada objetiva, se houver nova etapa

Não reconstruir busca, worker, score, outbox ou diálogos. A próxima etapa externa é homologar os provedores/configuração de destino e avaliar qualidade comercial com casos reais autorizados. Exige credenciais, ambiente e autorização próprios; não se considera comprovada por fixtures.

Reproduzir: pytest; npm test/build/typecheck:e2e; scripts/validate_browser_v137.py grupos a/b em portas novas; scripts/checkpoint_v137.py --base BASE --verify; scripts/verify_release.py --base BASE. O checkpoint local de hashes fica em artifacts/v137-checkpoint.json e o manifesto distribuído em RELEASE-MANIFEST.json. Dados temporários das fixtures não devem ser reaproveitados na instalação pessoal.

Pendências externas e capacidades parciais estão delimitadas em EXTERNAL-LIMITS-v1.37.md. Não há tarefa de implementação local restante listada como concluída sem evidência; limites do runner Vitest, MapLibre, dispositivos físicos e produção são declarados no relatório.
