# ScoutLIQ — Handoff v1.38.8-dev

## Fonte principal e estado da entrega

Repositório: https://github.com/gdsantos-dev/ScoutLIQ. Branch principal: `main`.
Base confirmada: `d8d717a14a03ee60a3f3719881d0fb0553162a4d`. Desenvolvimento: `codex/v1.38.8-operacao-diaria`.
O GitHub é a fonte principal. ZIPs e `work/` são históricos; não aplicar essas cópias sobre o checkout.

**Visibilidade reconfirmada em 31/10/2026: pública**, pela API autenticada. A consulta anterior ao conector também reportou pública. A documentação anterior dizia privada. A visibilidade não foi alterada; sua decisão permanece com o proprietário. O momento e a causa da divergência não foram inferidos.

## O que mudou

- SmartSearch admite a investigação automática opt-in em um lote progressivo canônico ligado à pesquisa e à rotina. Limites, cancelamento, fencing, ledger e orçamento continuam no worker compartilhado.
- Atingir a meta de incorporações impede nova descoberta, mas permite concluir o lote já admitido dentro da janela, consentimento e orçamento.
- Radar → Fila comercial → Operação do dia mostra meta, origens, investigações, qualificação, pesquisas, decisões e operações recuperáveis. Prioriza respostas, revisão, contexto alterado, dados pendentes e bloqueios a partir dos índices existentes.
- Seleção de até 50 empresas permanece entre visões e após operações. Versões são atualizadas para a próxima prévia; cada operação ainda exige confirmação explícita. O detalhe reutiliza essa seleção para investigar.
- Nenhum novo Score, scheduler, formulário de comunicação, integração paga ou serviço. Não houve envio comercial.

A meta diária mantém a definição de 1.38.7: empresas novas reais de todas as origens, sem duplicatas, demonstração ou descartes explícitos. A atribuição ao plano é uma medida separada. Investigadas e qualificadas são estados atuais; não são vendas ou conversões.

## Validação e documentação

Resultados executados e evidências: [VALIDATION](docs/VALIDATION-v1.38.8-dev.md) e `docs/qa-v1.38.8-dev/`.
Contratos e limites: [ARCHITECTURE](docs/ARCHITECTURE-v1.38.8-dev.md). Auditoria da base: [FLOW-AUDIT](docs/FLOW-AUDIT-v1.38.8-dev.md).
Mudanças: [CHANGELOG](docs/CHANGELOG-v1.38.8-dev.md); relação de arquivos: [CHANGED-FILES](docs/CHANGED-FILES-v1.38.8-dev.md).

A revisão Alembic continua **033**. Não há migração nova. Autenticação, políticas de contato, Score 3.0, evidências, histórico e configuração dos planos foram preservados.

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

## Limitações e próximos passos

- Implementado e validado localmente com SQLite e adaptadores sintéticos. PostgreSQL, Docker/Railway, produção/HTTPS, provedores reais, Safari, dispositivos físicos e leitores de tela continuam sem homologação externa.
- Um lote progressivo por pesquisa, com o menor teto da busca e das preferências atual/capturada, até 25 empresas. Excedentes permanecem disponíveis para investigação manual autorizada. Sem backfill de pesquisas antigas.
- A fila atualiza até 250 índices locais por chamada e informa cobertura pendente. Resultados refletem o estado atual do estoque; exclusão de registros, mudança de fuso e descartes anteriores à observação de 033 limitam comparações históricas.
- Consultas mostram até 20 pesquisas abertas/recentes, cinco decisões e cinco operações do dia; avisos indicam truncamento e os históricos canônicos permanecem acessíveis.
- Qualidade comercial, custo monetário, lucratividade e economia de tempo não foram medidos em operação real.
- Permanecem os avisos conhecidos de Starlette/anyio e do chunk de mapa do Vite. Dependências não foram atualizadas; os lockfiles foram auditados neste ciclo.
- Próximo passo: revisar o PR e decidir a integração. Depois, homologar em ambiente de teste os provedores e infraestrutura pretendidos, com credenciais e autorizações próprias. Nenhuma homologação implica autorização de contato.
- Avaliar separadamente a divergência de visibilidade do repositório. Não modificá-la sem autorização.

Não houve merge, deploy, alteração de banco pessoal, geração de ZIP ou envio comercial. Nas próximas entregas, conferir `origin/main`, usar branch `v<versao>-<funcao>` (ex.: `v1.38.9-confiabilidade`), commits e PR, seguindo [CONTRIBUTING](CONTRIBUTING.md).
