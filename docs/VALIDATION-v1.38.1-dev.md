# Validação — ScoutLIQ v1.38.1-dev

24/10/2026. Implementação em cópia isolada de work/v1.38-dev/ScoutLIQ, extraída do FULL integrado exato. SHA256 da base: f66a5097486760825f3f3ba1b33c5cab7036a81bd1ce282010b414afe916232b. Instalação pessoal, fontes históricas e bancos de produção não foram alterados.

## Resultado efetivo

| Verificação | Resultado |
| --- | --- |
| Backend completo, incluindo migrações e segurança existentes | **373 aprovados**, zero falhas/erros, 342,15 s |
| Frontend unitário existente | **23 aprovados** em 7 arquivos |
| TypeScript + Vite | Aprovado; build em 34,53 s |
| Tipagem dos E2E | Aprovada, inclusive após ampliar o teste de idiomas |
| Chrome E2E em oito hosts sintéticos | **31 aprovados** |
| Tags OSM malformadas | Teste focal aprovado após o ajuste defensivo final |
| Arquivos protegidos | **42 hashes iguais** à base integrada |
| Dependências | Lock frontend inalterado salvo versão do produto; dependências Python preservadas |

| Suíte E2E | Resultado |
| --- | --- |
| general-search | 3 aprovados |
| unified-search | 9 aprovados |
| map-search | 1 aprovados |
| smart-search | 3 aprovados |
| absorption | 5 aprovados |
| autonomy | 2 aprovados |
| experience | 3 aprovados |
| workflow | 5 aprovados |

A primeira regressão passou em 371 testes backend. A rodada final acrescentou os casos de alocação da investigação e retomada histórica, com 373 aprovações. Após iniciar essa rodada, foi acrescentada uma guarda para tags OSM com formato inválido; o caso específico foi novamente executado com resposta malformada. Não se confundem execuções repetidas com testes adicionais distintos. Os 31 E2E foram repetidos após a otimização de consultas e passaram novamente.

Os dois avisos backend são de depreciação de TestClient/httpx e AnyIO. Vite mantém aviso de chunk acima de 500 kB (mapa ~1.024 kB minificado); não houve remoção do alerta nem alegação de correção de performance desse bundle. No Playwright aparece o aviso de NO_COLOR/FORCE_COLOR. Nenhum deles foi contado como falha ou ocultado.

## Interface e evidências

O formulário foi verificado em 1440, 390 e 320 px, sem overflow horizontal: larguras internas/scroll 598/598, 388/388 e 318/318. Teclado, Escape, devolução de foco, preferência por movimento reduzido e critérios sem nichos foram exercitados. Axe encontrou zero violações nos critérios WCAG 2 A/AA e 2.1 AA avaliados nessa tela. Isso não equivale a homologação com leitor de tela ou dispositivo físico.

- [Formulário desktop](evidence-v1381/general-form-1440.png)
- [Formulário mobile](evidence-v1381/general-form-390.png)
- [Formulário 320 px](evidence-v1381/general-form-320.png)
- [Resultados desktop](evidence-v1381/general-results-desktop.png)
- [Resultados mobile](evidence-v1381/general-results-mobile.png)
- [Critérios em inglês](evidence-v1381/criteria-en-US.png) e [espanhol](evidence-v1381/criteria-es.png)
- [Relatório estruturado](evidence-v1381/validation.json), [JUnit completo](evidence-v1381/backend-final.xml) e [axe/reflow](evidence-v1381/accessibility.json)

Capturas de formulário mobile e resultados desktop/mobile foram também inspecionadas visualmente. As empresas com QA são dados sintéticos; a captura não demonstra qualidade comercial real.

## Integridade e segurança

Absorção (backend, frontend, testes), todas as migrações até 028, Score 3.0, CommercialFit, research_worker, main, App e Pipeline estão preservados por hash. Não existe migração 029 neste ciclo. A regressão exercita instalação limpa, upgrades, preservação de registros e proteções contra downgrade destrutivo em SQLite descartável. PostgreSQL/produção não foram homologados.

Os novos testes cobrem ausência de chamada sem suporte, localização inválida, separação por usuário, idempotência, pausa/retomada/cancelamento, orçamento, coleta parcial, exclusões e ausência de criação de outbox/draft ao iniciar busca geral. Autenticação, CSRF, autorização por objeto, mass assignment, concorrência e políticas de comunicação também permanecem na regressão completa. Não há novos destinos externos, secrets frontend ou dependências de runtime. Revisão de segurança do escopo está no [contrato](GENERAL-SEARCH-v1.38.1-dev.md#segurança-e-custo-do-ciclo); auditoria externa atual de vulnerabilidades não foi realizada.

## Empacotamento e reprodução

FULL e PATCH são de fontes, com documentação, testes e lockfiles. Excluem .env real, bancos, caches, node_modules, dist e runtime. O PATCH parte exclusivamente da v1.38.0-dev integrada. O script package_general_v1381.py exige o hash da base e compara os módulos protegidos.

A verificação de empacotamento produz release/PACKAGE-VALIDATION.json e SHA256SUMS.txt. Em cópias descartáveis ela confere extração/manifesto, dry-run sem gravação, recusa de customização conflitante, equivalência PATCH/FULL, preservação de .env e banco sintéticos, recusa de reaplicação e restauração das fontes originais pelo backup. Esse teste não migra banco nem realiza deploy.

Comandos e instruções estão em [INSTALL-v1.38.1-dev](INSTALL-v1.38.1-dev.md). O manifesto DEV-OVERLAY herdado e documentos v1.37/v1.38 descrevem etapas anteriores; RELEASE-MANIFEST.json e os documentos v1.38.1-dev correspondem a este pacote.

## Estado da entrega

- **Implementado e testado localmente:** exploração geral, nichos opcionais, modos explícitos, cobertura, distribuição secundária à qualidade, salvamento/histórico, monitores e rotinas compatíveis.
- **Cobertura parcial por contrato:** apenas categorias comerciais existentes na fonte; OSM exige geografia observada no mapa e não aceita o limite administrativo selecionado. Não é censo nem promessa de completar a meta.
- **Não homologado externamente:** Geoapify/Overpass reais, qualidade/conversão comercial, produção, PostgreSQL, HTTPS de hospedagem, OAuth e canais comerciais reais, Safari e dispositivos físicos.
- **Bloqueios locais:** nenhum para os cenários deste ciclo. Homologação externa depende de ambiente/credenciais e execução autorizada; nenhuma cota de descoberta real foi consumida pelos testes controlados.

Não houve deploy, atualização de banco de produção, contato comercial ou alteração automática do Score. Próximo passo recomendado: amostragem externa pequena e autorizada, seguida de revisão humana e medição comercial, conforme o [contrato](GENERAL-SEARCH-v1.38.1-dev.md).
