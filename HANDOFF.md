# ScoutLIQ — Handoff v1.38.7-dev

## Fonte principal e escopo desta publicação

Repositório privado: https://github.com/gdsantos-dev/ScoutLIQ. Branch principal: `main`.
A partir desta publicação, o GitHub e o histórico Git são a fonte principal do código. ZIPs anteriores são artefatos históricos; não desenvolver sobre `work/` nem aplicar um ZIP por cima de alterações do Git.

Base importada: `ScoutLIQ-v1.38.7-dev-FULL.zip`, SHA-256 `2f067f93aa5ae17214ef4da7a798b17fea8beab45eb0ed46cf47dfed876bd9ac`.
Commit da importação fiel: `7f7c4db2ce7bc10b3b1887d785da848b8f22c0f8`. Os 779 arquivos do FULL foram comparados com o conteúdo do índice Git antes desse commit. A pasta externa `ScoutLIQ/` do ZIP corresponde à raiz do repositório; caminhos internos foram preservados.

Esta etapa acrescenta documentação e proteção de versionamento. Não altera backend, frontend, testes, dependências, migrações ou funcionalidades. Os manifestos de release existentes continuam descrevendo o FULL original, anterior aos ajustes de documentação e `.gitignore`; não devem ser reinterpretados como manifestos de todos os commits futuros.

## O que está desenvolvido

Aplicação de prospecção comercial da ORLIQ: React/TypeScript/Vite no frontend, FastAPI/SQLAlchemy/Alembic no backend, com pesquisa, Score 3.0, evidências, Radar, Pipeline/CRM, Sites, absorção, investigação, operações comerciais, acompanhamento, aprendizado supervisionado e infraestrutura de comunicação.

A v1.38.7-dev acrescentou planejamento diário em Automações, desativado por padrão: metas, pesquisas e localizações autorizadas, prioridades, janela/horários, limites persistentes, consentimento vinculado à prévia, pausa/retomada/desativação, progresso, histórico e sugestões baseadas nos indicadores existentes. Reutiliza rotinas, ledger e worker; não cria um motor de score ou scheduler concorrente. A migração aditiva é **033 sobre 032**.

Fontes principais: `backend/prospecting.py`, `backend/prospecting_models.py`, `migrations/versions/033_prospecting_plans.py`, `frontend/src/components/ProspectingPlan.tsx`. Consulte [arquitetura](docs/ARCHITECTURE-v1.38.7-dev.md), [métricas](docs/METRICS-v1.38.7-dev.md) e [changelog](docs/CHANGELOG-v1.38.7-dev.md).

## O que foi testado

Evidências da entrega local anterior à publicação, preservadas em `docs/qa-v1.38.7-dev/` e [VALIDATION](docs/VALIDATION-v1.38.7-dev.md):

| Verificação da versão | Resultado registrado |
|---|---|
| Backend completo | 592 testes aprovados |
| Frontend unitário | 27 testes aprovados |
| TypeScript aplicação e E2E | Aprovado |
| Build Vite | Aprovado |
| Navegador Chromium | 77 E2E em 18 suítes, incluindo mobile, teclado, Axe e recuperação |
| FULL extraído em ambiente limpo | 79 testes aprovados |
| Preservação dos mecanismos existentes | 61 fontes/migrações canônicas idênticas à base |
| Agregações de progresso | 1.000 e 10.000 empresas; 8 consultas em ambos os casos |

Nesta publicação foram revalidados hash/CRC do FULL, manifesto interno, igualdade integral do commit de importação, ausência de runtime no índice, revisão de candidatos a segredos e restrições de `.gitignore`. A regressão funcional não foi reexecutada nesta etapa: não houve alteração funcional. Isso não é uma execução de CI no GitHub nem homologação externa.

O PATCH anterior foi validado por equivalência com o FULL, proteção de runtime, recusa de conflitos/reaplicação e rollback de fontes. Os recibos independentes dessa entrega estão em `docs/github-publication/`. Referem-se ao ZIP original, não a uma nova execução nesta publicação.

## Execução local a partir do GitHub

Pré-requisitos de referência: Git/GitHub autenticado, Python 3.12 e Node.js 22, conforme Dockerfile e lockfiles existentes.

```powershell
gh repo clone gdsantos-dev/ScoutLIQ
cd ScoutLIQ
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
npm run build
cd ..
```

Edite `.env` somente localmente: mantenha `APP_ENV=development`, `APP_ORIGIN=http://localhost:8000`, banco local em `data/`, `DEMO_SEED=false`, `RESEARCH_EXECUTION_MODE=worker` e `SCOUTLIQ_PROCESS_MODE=combined`. Defina `ADMIN_EMAIL` e uma senha exclusiva forte com pelo menos 12 caracteres. Use `EMAIL_MODE=console` no desenvolvimento sem Brevo; mensagens de teste ficam no log local, que não deve ser publicado. Não configure credenciais reais para apenas inspecionar o código. Nunca sobrescreva um `.env` ou banco existentes.

```powershell
.venv/Scripts/python.exe scripts/start.py
```

O supervisor existente prepara o diretório de dados, executa Alembic até `033`, faz o bootstrap e inicia web/worker. Interface em http://localhost:8000. Abrir Automações não ativa o plano: revisar e confirmar é obrigatório. Não configurar provedores ou ativar pesquisas sem revisar cotas e condições de uso. Para testes, usar bancos isolados e `requirements-dev.txt`; não apontar fixtures para dados pessoais.

Para atualizar uma instalação existente, faça backup consistente do banco, pare os processos, atualize fontes/dependências e siga [INSTALL](docs/INSTALL-v1.38.7-dev.md). Nunca remover dados para contornar o bloqueio de downgrade da migração 033.

## Limitações e problemas conhecidos

- Implementado e testado localmente; PostgreSQL, provedores reais, Docker/Railway, produção/HTTPS, Safari, dispositivos físicos e leitores de tela não estão homologados por essa evidência.
- Qualidade comercial real, custo monetário e lucratividade dependem de observação externa; não foram inferidos de fixtures.
- Descartes anteriores à observação da migração 033 não têm cobertura histórica completa. Exclusões de dados e alterações de fuso podem afetar comparações históricas.
- Um plano por conta; até 20 pesquisas; no máximo uma execução por pesquisa/dia; cooldown mínimo de 24 h; janela dentro do mesmo dia; histórico limitado a 366 dias/200 decisões e até 200 opções exibidas.
- Avisos preexistentes de depreciação Starlette/anyio e tamanho do chunk de mapa do Vite. Não houve atualização de dependências nesta publicação nem nova auditoria externa de CVEs.
- Documentos e empacotadores antigos são históricos. Os scripts de empacotamento incremental precisam dos ZIPs-base fora do Git; não são necessários para executar o aplicativo.
- Não foi criado pipeline de CI nem configurado deploy automático. A presença de Dockerfile e railway.toml não representa deploy realizado.

## Segurança da publicação

Nenhum `.env` real, senha/token de serviço, banco, sessão, chave privada, cache, dependência instalada ou backup foi incluído. `.env.example` contém campos de segredo vazios. Constantes de autenticação das fixtures são sintéticas, restritas aos testes, e não são credenciais da instalação. A revisão de padrões não equivale a uma auditoria exaustiva de segurança. O Git usa identidade noreply para não expor o e-mail pessoal do autor.

Não houve deploy, mudança em banco pessoal, consumo de cotas de prospecção ou envio comercial. As integrações continuam exigindo configuração própria e autorização de contato.

## Próximos passos

1. Trabalhar a partir de `main` atualizada, em branches `codex/<assunto>`, com commits descritivos e revisão por pull request. Ver [CONTRIBUTING](CONTRIBUTING.md).
2. Em cada alteração funcional, executar testes proporcionais e atualizar o relatório com o que realmente foi testado. Preservar evidências e migrações existentes.
3. Preparar CI com bancos sintéticos, sem credenciais reais, em uma alteração separada; não considerar a ausência de CI uma falha funcional desta versão.
4. Homologar PostgreSQL/provedores/produção somente em ambiente apropriado, com credenciais próprias, revisão de segurança e autorização correspondente.
5. Continuar a evolução comercial a partir dos limites documentados, sem reimplementar planejamento, worker, Score 3.0 ou infraestrutura de comunicação.

ZIPs futuros, quando solicitados, devem ser gerados do commit revisado do GitHub e identificar seu SHA. Não usar ZIPs ou cópias locais antigas como fonte principal.
