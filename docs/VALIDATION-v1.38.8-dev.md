# Validação — v1.38.8-dev

Fechamento: 31/10/2026. Evidências locais em SQLite, adaptadores sintéticos e Chromium. Os logs e capturas preservam o relógio do host de execução. Sem homologação externa, deploy ou envio comercial.

| Verificação executada | Resultado |
|---|---|
| Backend completo | 606 aprovados; 14 casos novos; dois avisos conhecidos |
| Regressão focal após alinhamento final do motivo da fila | 145 aprovados; inclui contratos diários, revisão, acompanhamento, planejamento e investigação |
| Frontend unitário | 27 aprovados em oito arquivos |
| TypeScript aplicação e E2E | Aprovados |
| Vite | Build concluído; aviso conhecido do chunk de mapa |
| Chromium | 79 aprovados em 19 suítes; jornada diária repetida após o ajuste final |
| Dependências Python / npm | Nenhuma vulnerabilidade conhecida reportada nas consultas executadas sobre os lockfiles |
| Preservação | 42 arquivos de modelos, migrações, worker, investigação e dependências idênticos à base Git |
| Migração | Continua 033; sem alteração de schema |

## Cenários novos e regressão

Os 14 casos em `tests/test_daily_operations.py` cobrem descoberta vinculada à investigação progressiva, conclusão do lote ao atingir a meta, ledger, pausa, revogação de claim, orçamento zero/esgotado, reencontro sem duplicação, ordenação e motivo, estados humanos, resultados vazios, dados insuficientes, versões, idempotência, ausência de draft/outbox implícitos, autenticação, isolamento de usuários, limites de entrada e recuperação de lease com fencing.

A jornada Chromium confirma plano autorizado → descoberta → investigação → fila diária → revisão → preparação de dois rascunhos. Fecha/reabre a página durante o worker, verifica configurações preservadas, versões e seleção entre operações, atalho da investigação e status `draft`, sem outbox/envio. A revisão final usa exatamente o critério SQL da prioridade também no motivo apresentado.

Mobile em **320, 390 e 768 px**, desktop em **1440 px**: sem overflow horizontal nos cenários, seleção por teclado, foco, movimento reduzido, Axe WCAG A/AA, erro 503 e recuperação sem perder seleção. Capturas revisadas visualmente em `qa-v1.38.8-dev/daily-*.png`. Não equivale a homologação de leitor de tela ou dispositivo físico.

As 18 suítes históricas incluem busca geral/nicho opcional, busca unificada, mapa, absorção, recuperação, autonomia, experiência, workflow, redesign, aprendizado, inteligência, comunicação, investigação, fila comercial, acompanhamento, indicadores e planejamento. A definição da meta mantém todas as origens; o E2E diário verifica três empresas novas no dia, duas atribuídas ao plano, para meta dois.

## Volume e custos

A medição controlada de 1.000 empresas registrou 39 consultas SELECT e atualização de até 250 índices. As 750 empresas restantes são informadas como cobertura pendente. Amostras observadas de 1,979 s, 1,427 s e 0,900 s estão em `qa-v1.38.8-dev/volume-samples.json`, com a última medição em `daily-volume.json`; o tempo depende do equipamento e da carga. Zero chamadas a provedores nessa consulta. Não é SLA, medição PostgreSQL ou demonstração de qualidade comercial.

A meta, investimento em investigação, cotas e operações continuam definidos pelos contratos existentes. Não se estimaram custo monetário, lucratividade ou economia de tempo a partir de fixtures.

## Segurança revisada

| Área | Resultado e limite |
|---|---|
| Secrets e dados | Revisão dos arquivos alterados e padrões de chave/token, sem achados; somente dados sintéticos nas evidências. `.env`, bancos, credenciais e logs de servidor não integram a publicação. Busca por padrões não garante detecção de todo segredo possível. |
| Autenticação, CSRF, autorização, IDOR/BOLA | Dependências de autenticação e CSRF preservadas. Filtros de proprietário, UUIDs e joins controlados na projeção; testes 401, dados de outra conta e seleção por IDs. |
| Mass assignment / privilege escalation | Enums, limites e campos permitidos; nenhum campo de proprietário, papel, plano de cobrança ou privilégio aceito por este ciclo. |
| SQL / NoSQL | ORM parametrizado, escape dos filtros de texto e sem operadores arbitrários. Nenhuma nova integração NoSQL. |
| XSS / dados externos | Texto renderizado pelo React; nenhum HTML arbitrário ou nova fonte externa. |
| Rate limit, concorrência, recuperação | Limites existentes, lock por usuário, até 50 IDs, até 250 índices por chamada, leases e fencing, idempotência e cancelamento cobertos. |
| Sessões, cookies, CORS, headers, logs e erros | Implementações existentes preservadas e submetidas à regressão; sem credenciais ou stack traces novos expostos pela interface. |
| SSRF / command injection / deserialização | Não foi adicionado cliente externo, comando com entrada do usuário, eval ou desserializador executável. Investigação usa as proteções canônicas. |
| Upload, webhook, pagamentos e endpoints administrativos | Nenhuma nova superfície nesse ciclo. Controles existentes permanecem. |
| Dependências | Lockfiles sem alteração de versões; auditorias Python/npm sem avisos de vulnerabilidade conhecidos na consulta. |
| HTTPS e produção | Não verificados neste ciclo local; sem deploy. |

## Repetições e limites da evidência

A primeira execução completa apresentou 565 aprovados e 41 erros de preparação por acesso negado ao temporário global do Windows. A execução com `--basetemp` e TEMP/TMP isolados concluiu os 606 testes. Não se alteraram testes de migração para suprimir falhas.

Um E2E histórico usava `SCOUT_TEST_PYTHON`, enquanto o runner fornecia somente `E2E_PYTHON`. O runner novo fornece ambos a partir do mesmo interpretador. Um seletor do teste diário foi corrigido para o papel/nome acessível real. A revisão focal final detectou três falhas causadas pela conversão involuntária UTF-8/cp1252 em dois arquivos; a codificação foi restaurada sem mudar as expectativas dos testes. O fixture diário passou a aguardar estados persistidos, corrigindo uma corrida no limite de segundos sem desativar intervalos ou cotas. As execuções finais aprovadas substituem essas tentativas; não representam correção de provedor real.

A regressão completa e as 19 suítes foram executadas; depois do alinhamento final entre prioridade e motivo, foram repetidos os contratos afetados e a jornada diária. Os recibos identificam cada execução sem somar repetições ao número de casos únicos.

**Implementado/testado localmente:** continuidade, visão diária, filtros, motivos e preservação da seleção. **Delimitado/parcial:** um lote progressivo por busca; excedentes manuais; sem backfill; cobertura de índices limitada por chamada; listagens truncadas com aviso; descartes históricos e mudança de fuso. **Não homologado externamente:** provedores, PostgreSQL, Docker/Railway, HTTPS/produção, Safari, leitores de tela, dispositivos físicos e qualidade comercial real.

O repositório foi reconfirmado público via API em 31/10/2026, contrariando a documentação original. Visibilidade não alterada. Nenhuma falha relevante conhecida deve ser omitida deste relatório.

## Reprodução

Usar `requirements.lock`, `requirements-dev.txt` e `npm ci`; Python isolado e bancos de teste. A instalação permanece descrita no HANDOFF. Em Windows, escolher caminhos de temporário novos dentro do workspace.

```powershell
python -m pytest -q --basetemp artifacts/pytest-novo
npm --prefix frontend test
npm --prefix frontend run build
node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.e2e.json
python scripts/validate_browser_v1388.py --group complete --port 9500
python scripts/validate_browser_v1388.py --group commercial --port 9520
python scripts/validate_browser_v1388.py --group followup --port 9522
python scripts/validate_browser_v1388.py --group operations --port 9524
python scripts/validate_browser_v1388.py --group planning --port 9526
python scripts/validate_browser_v1388.py --group daily --port 9528
```

O runner recusa portas cujo banco sintético já exista. Não apagar dados pessoais para repetir testes. Os recibos e hashes das evidências ficam em `qa-v1.38.8-dev/`.
