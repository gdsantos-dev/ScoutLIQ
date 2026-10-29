# Validação — ScoutLIQ 1.20.0

27/09/2026. Base técnica: hotfix 1.19.1 fornecido. Direção de UX: handoff premium Markdown. Execução local em Windows, Chrome, React/Vite e FastAPI/SQLite. Os bancos de teste e prévia são separados da configuração normal da aplicação.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Python: backend e atualização de release | **107 passaram**: 97 testes existentes + 10 testes do instalador |
| Vitest | **6 passaram**, em 2 arquivos |
| TypeScript da aplicação e build de produção | Passaram |
| TypeScript estrito dos cenários de navegador | Passou |
| Playwright | **20 passaram**, 0 falhas, em 7,1 minutos |
| Dependências npm | Nenhuma vulnerabilidade conhecida reportada em 223 dependências |
| Dependências Python fixadas | Nenhuma vulnerabilidade conhecida reportada em 24 pacotes de `requirements.lock` |
| Backend e migrations contra o ZIP original | **38 arquivos idênticos por SHA-256**; Alembic em `018`, sem nova migration |
| Pacote completo e patch | Aplicação sobre cópia da base validada; verificação final dos arquivos em `artifacts/release-validation.json` |

## Cobertura de interface

- Operar e Gerir clientes, lembrança da última área, todos os destinos e comandos por teclado; busca sem dependência de acentos, campanhas por comando e encaminhamento de pesquisa.
- Painel de contexto: abertura/fechamento, devolução de foco, tabs por teclado, dados carregados por seção, score e pesquisa.
- Fluxo persistido: cadastrar empresa, acompanhar, salvar oportunidade, próxima ação e data, contato, negociação, venda, recebimento parcial, custo e exportação.
- Sites: cadastro, calendário, margem, edição, recarga, detalhe mobile e remoção do registro criado pelo próprio teste.
- Busca territorial com resposta controlada, busca salva, frequência semanal persistida, reexecução e isolamento da lista de Oportunidades.
- Campanha: criação, inclusão de empresa, pausa e seleção por comando. Automação: criação, pausa, persistência e contraste do estado pausado.
- Pesquisa: início explícito, auditoria profunda, enriquecimento, reanálise e resposta de erro. Fixtures tipadas respeitam os contratos da API; não representam execução comercial real de provedores externos.
- Falha de API, tentativa posterior, aviso offline e sessão expirada.
- Idiomas português/inglês/espanhol, preferências persistidas, moeda e identidade crimson.
- Lista sintética com 2.000 empresas: renderização progressiva de 60 para 120 itens, clusters ativos e quantidade limitada de marcadores.
- Autenticação: login real inicial, erro de credenciais, visibilidade de senha, formulários de recuperação/cadastro, alvos e ausência de overflow. Criação, confirmação e redefinição de contas também são cobertas nos testes de backend; envio real de e-mail não foi executado.

## Responsividade e acessibilidade

Larguras verificadas: **320, 375, 390, 393, 430, 768 e 1920px**, além do desktop em 1440px. Navegação, mapa/painel de resultados, contexto e destinos de gestão são exercitados em cada largura. As capturas aguardam o conteúdo e o gráfico carregarem. O teste rejeita overflow horizontal da página e diálogos fora da viewport.

`axe-core` executa regras WCAG 2 A/AA e 2.1 AA nas principais telas, formulários e estados; a rodada final não reportou violações nas superfícies examinadas. A preferência de movimento reduzido é exercitada. Teclado, Escape e foco têm verificações próprias. Essas verificações automatizadas e a inspeção visual não equivalem a certificação de acessibilidade nem a uma auditoria com todos os leitores de tela.

## Performance

Entrada JS: aproximadamente **424 kB / 135 kB gzip**. O contexto é carregado sob demanda (35 kB / 10 kB gzip); gráficos também (374 kB / 110 kB gzip). Fonte Inter local latina: 48 kB. A lista não monta todas as empresas simultaneamente; o mapa agrupa pontos próximos na viewport e utiliza um worker.

O build mantém um aviso conhecido: o chunk MapLibre tem aproximadamente **1.024 kB / 279 kB gzip**, além do worker separado. O aviso não foi ocultado. Não foram aferidos Core Web Vitals em rede móvel real nem consumo em dispositivos físicos de baixo desempenho.

## Segurança e atualização

Consulte [SECURITY-REVIEW-v1.20.md](SECURITY-REVIEW-v1.20.md). O backend, a autorização por objeto, os DTOs, os scores e as transações financeiras foram preservados. O patch exige hashes da base, faz pré-validação integral e backup antes de alterar fontes. Testes simulam conflito local, payload corrompido, caminho inválido e falha durante cópia com restauração.

O ensaio do pacote aplica o patch a uma cópia extraída do ZIP original e compara cada fonte com o manifesto do pacote completo. Também verifica preservação de `.env`, banco e cache de compilação, backups, recusa de reaplicação e recusa sem escrita quando há personalização local. Dados de runtime, dependências instaladas, logs e relatórios não entram nos ZIPs de fontes.

## Evidências e reprodução

- `artifacts/pytest-final.txt`, `vitest-final.txt`, `build-final.txt`, `e2e-final.txt`.
- `artifacts/playwright-report/index.html`: relatório navegável; `artifacts/redesign/`: capturas desktop/mobile.
- `artifacts/npm-audit.json`, `pip-audit.json`, `release-validation.json`.
- `release/SHA256SUMS.txt` e `release/CHANGED-FILES.json`: integridade dos ZIPs e relação exata das mudanças.
- Comandos de execução e prévia: [README](../README.md). Aplicação do patch: [PATCH-v1.20.md](PATCH-v1.20.md).

## Limites da entrega local

Não foram realizados deploy, homologação Railway/HTTPS, execução Docker, PostgreSQL, testes em Safari/Firefox/dispositivo físico nem envio real Brevo. MapTiler com chave de produção, Geoapify, Brave e outros provedores externos precisam de homologação com as credenciais do ambiente de destino. O mapa OpenStreetMap foi carregado no navegador local.

Os testes Python exibem dois avisos de depreciação vindos de Starlette/httpx e AnyIO, sem falhas. A infraestrutura de produção e seus dados não foram alterados.
