# Checkpoint verificável — v1.36.0

Base exclusiva: FULL v1.35.0 SHA256 `2e5bac34cbe21dd40224991fa874a58655b5863847b1ac0efcdc3e8cf51981f6`. Diretório de trabalho: work/v1.36.0/ScoutLIQ. Nenhum backend ou migração alterado: 74 arquivos idênticos; head 026. Instalação pessoal preservada.

## Consolidado

Shell/CSS Module, navegação desktop e compacta até 1024; Radar em lista e mapa sob demanda; memória de filtros/ordem/quantidade entre superfícies; ficha por etapas mantendo rascunhos; critérios de busca visíveis e edição progressiva; estado de rotinas; comunicação com configuração/conexão e autorização preservadas. Tokens unificados e 377 seletores substituídos/removidos. Ver CHANGELOG-v1.36.md, FEATURE-MATRIX-v1.36.md e VALIDATION-v1.36.md.

265 backend + 23 unitários frontend + 43 E2E distintos passaram. Build e tipos aprovados. Auditorias de dependências sem vulnerabilidades conhecidas. FULL/PATCH têm manifesto e verificação isolada em artifacts/release-validation.json; arquivos finais em release/. SHA256SUMS.txt identifica o pacote exato.

## Retomada sem refazer fatias concluídas

1. **Paridade de idiomas:** SmartSearch já tem novas entradas e critérios traduzidos. Inventariar os textos ainda PT em SmartSearch, OperationalRoutines, OpportunityWorkflow, CommercialLearning, ScoreCalibration e Communication. Migrar frases completas para o dicionário e definir a fronteira de mensagens de servidor, sem traduzir conteúdo/evidência do usuário. Repetir EN/ES nos estados de revisão, erro e progresso; teste atual cobre entradas de busca, não a totalidade.
2. **Consolidação de CSS restante:** shell e etapas usam módulos; Radar tem stylesheet próprio. Demais páginas seguem globais herdados. Migrar por superfície e regressão; não rodar novamente consolidate_frontend_css.cjs na v1.36. Não apagar seletores apenas por conterem product-shell: isso removeu o editor mobile na primeira rodada, já corrigido.
3. **Validação com operador:** testar com casos ORLIQ revisados reais e medir tempo/cliques/erros de decisão. E2E e capturas não comprovam qualidade comercial ou conversão. Não alterar Score automaticamente.
4. **Homologações externas:** dependem de ambientes/credenciais/autorizações reais; Gmail real, HTTPS/deploy, dispositivos e leitor de tela. WhatsApp Cloud adapter é pendência funcional herdada, fora da camada visual. Não realizar envios por conta da entrega de UX.

## Reprodução

Seguir INSTALL-v1.36.md. Builds precisam estar concluídos antes de testes. Relatórios Playwright separados por grupo; fixtures de comunicação limpas para não acionar o limite real por fila residual. Manter limites, CSRF e guardas ativos. Os 43 cenários são 40 herdados + 3 novos, sem contar reruns duas vezes.

Ao continuar, inspecionar release/SHA256SUMS.txt e os logs finais antes de alterar. Não retornar a v1.29/1.33; não reconstruir supervisor, Score, ledger, aprendizado ou outbox. Não tratar as pendências acima como funcionalidade já homologada.
