# Validação local — ScoutLIQ 1.32.0

Datas: 2026-10-15 e 2026-10-16. Base isolada do FULL 1.31.0, conferida por hash/manifesto antes da extração. Nenhum banco pessoal foi copiado para QA. Dados, contas, empresas e provedores usados nos ensaios são sintéticos.

## Resultados registrados

- Regressão backend completa final: **164 passaram**, sem falhas, em 173,64 segundos. Inclui migrações e rejeição de revisão comercial com versão antiga. Log: `artifacts/pytest-release.txt`.
- Frontend: **23 testes unitários passaram**, TypeScript de aplicação/E2E e build passaram.
- Auditorias de dependências: `npm audit` retornou código 0; `pip-audit -r requirements.lock --no-deps --disable-pip` não encontrou vulnerabilidades conhecidas na consulta desta execução.
- Navegador Chromium: **33 cenários distintos aprovados em rodadas complementares** — 30 legados na regressão geral e os três novos na rodada final de Busca Inteligente. Os dois cenários legados de Radar/layout mobile também foram repetidos e passaram após a correção do botão. Logs: `artifacts/e2e-v1.32.txt`, `artifacts/e2e-smart-release.txt` e `artifacts/e2e-smart-verified.txt`; os dois primeiros preservam as falhas intermediárias corrigidas, e o último registra 3/3 aprovados.
- Busca validada em 320, 390, 768 e 1440 px, sem overflow horizontal; auditoria axe sem violações nas regras WCAG selecionadas, Escape e movimento reduzido. Capturas desktop, mobile e resultados conferidas visualmente.
- O cenário persistente fechou a página, executou o worker em processo separado e recuperou duas qualificadas, uma descartada e duas investigadas; salvou a intenção e registrou revisão comercial. Fontes e investigações eram sintéticas.
- A repetição de logins atingiu o limitador HTTP (429). O host sintético foi reiniciado para a rodada final; a proteção não foi desativada.
- FULL e PATCH **verificados**: 239 arquivos de fonte, mais manifesto; 42 entradas no PATCH. A aplicação em cópia descartável da base 1.31.0 reproduziu todos os hashes do FULL, conservou `.env`, banco sintético e cache local, criou backup e recusou reaplicação/conflitos sem escrever. 40 arquivos de backend/migrações permaneceram idênticos à base. Evidência: `artifacts/release-validation.json`; reprodução: `scripts/verify_release.py`. Checksums distribuídos em `release/SHA256SUMS.txt`.

## Matriz de aceitação

| Requisito | Evidência local |
|---|---|
| A — 25/50/75/100 | Parametrização que exige exatamente a quantidade qualificada, sem contar investigação ou descarte. |
| B — redes em fontes diferentes | Mesmo `assess` e prioridade incompatível para Geoapify, OSM e manual; normalizador conserva entidade para motivo auditável. |
| C — público | Prefeitura descartada antes de investigação. |
| D — independente e útil | Necessidade/atividade/contato verificados ficam acima de rede; autonomia revisada permite exceção documentada. |
| E — insuficiência | `null` e estado insuficiente/provisório; não equivale a qualidade ruim da empresa. |
| F — site | Ausência registrada, desconhecido, falha e contradição testados separadamente. |
| G — score | Fixture anterior 2.5 congelada, nova fórmula e razões; migração confirma snapshot antigo e integridade de evidências. |
| H — internacional | Tecnologia em Austin/EUA expõe falta de categoria específica Geoapify; seletor OSM TI é reconhecido sem substituir por comércio. |
| I — deduplicação | Mesma identidade reutilizada; cidades/coordenadas conflitantes preservam homônimos e filiais. |
| J — progressão | Página com descartes, investigação, nova página, duplicata e esgotamento; limite de 12 páginas impede loop. |
| K — persistência | Estado e cursores no banco; claim expirado não grava, retomada usa novo token, prazo termina mesmo com orçamento diário esgotado. |
| L — compatibilidade | Suítes de autenticação, CRM, finanças, Sites, campanhas, automações, oportunidade e pesquisa continuam na regressão; controles legados do lote sincronizam a nova busca. |

## Correções motivadas pelos testes

- Telefone igual não bastava para distinguir filiais: coordenadas conflitantes agora impedem fusão, mesmo com nome/cidade/telefone iguais.
- Reversão de migração com reconstrução da tabela pai poderia disparar cascatas SQLite. A 021 usa DROP COLUMN nativo no downgrade; os testes verificam conservação de evidência e chaves estrangeiras.
- Campos ausentes na análise compacta eram convertidos em falsos sinais negativos. Campos efetivamente observados agora delimitam diagnósticos de nicho.
- O novo botão do Radar herdava bloqueio de ponteiro e o mapa interceptava cliques. A ação passou a receber eventos, com verificação nos layouts desktop e mobile existentes.
- Alterar a meta durante a interpretação podia exibir uma quantidade diferente da intenção retornada. Os campos ficam bloqueados durante a requisição; o teste cobre a troca seguida de execução.
- A revisão comercial exige a versão atual do cadastro; uma revisão antiga recebe 409 e não substitui encerramento, estágio ou opt-out. O teste de navegador usa o papel e o nome acessível observados dos seletores.
- Expectativas antigas que exigiam versão 2.5/valor 90 e descarte invisível dentro do Geoapify foram atualizadas para o comportamento explicitamente solicitado da 3.0 e adequação compartilhada. Os demais contratos técnicos permanecem verificados.

## Reprodução

Depois de instalar dependências e gerar o build:

```powershell
python -m pytest -q --basetemp=.runtime-tmp/pytest
npm test --prefix frontend
npm run typecheck:e2e --prefix frontend
npm run build --prefix frontend
python tests/smart_browser_fixture.py server
```

Em outro terminal, no frontend, configure `E2E_ORIGIN=http://localhost:8004` e `E2E_PYTHON` para o Python do ambiente e execute `npm run test:e2e`. O host e o worker de teste usam somente `data/e2e.db`; nunca execute scripts de QA sobre a instalação pessoal.

Logs, capturas e relatórios gerados ficam em `artifacts/`, fora dos ZIPs de código. O conjunto de avaliação reproduzível está em `tests/fixtures/commercial-evaluation-v132.json`.

## Limites da evidência

Fixtures não demonstram capacidade de encontrar 100 empresas reais qualificadas. Permanecem sem homologação: qualidade/cobertura atual de Geoapify/OSM/Brave, taxa de conversão, classificação humana em amostra real, tempo/custo externo, SMTP/Gmail/WhatsApp, PostgreSQL, Docker/Railway, domínio/HTTPS, supervisão 24/7, dispositivos físicos e leitores de tela. Há aviso de bundle grande do mapa já existente e depreciações da infraestrutura de testes Python; não foram confundidos com falhas de aplicação.
