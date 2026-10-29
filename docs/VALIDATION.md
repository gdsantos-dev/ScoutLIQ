# Validação local — ScoutLIQ V1

Data: 22/09/2026. Windows, Chrome, Python 3.12 e Node 24. Testes automatizados usam banco separado; nenhum dado de produção foi usado.

## Resultado

- Backend: **19 testes aprovados**, incluindo cookies e headers em modo produção, origem/CSRF, propriedade de objetos, DTOs, score, concorrência de recebimentos, idempotência, conflitos, Sites e seeds. Dois avisos de depreciação nas dependências de TestClient, sem falhas.
- Frontend: **3 testes aprovados** para valores em centavos e datas.
- Navegador: **6 cenários aprovados**. Cinco passaram na execução completa; o sexto (Sites) foi repetido e aprovado após corrigir o nome acessível do seletor Cliente. O relatório HTML mais recente corresponde à repetição focal de Sites.
- Navegação nas sete áreas e axe nas páginas internas: nenhuma violação detectada nas regras WCAG 2 A/AA e 2.1 AA selecionadas. Formulário de Sites também verificado por axe. Isto não substitui auditoria manual completa de acessibilidade.
- Fluxo real: cadastro → pipeline → venda → recebimento parcial → custo → exportação, com recarregamento e persistência.
- Sites: criação, alerta por vencimento, margem, edição, recarga, detalhe mobile e exclusão do registro sem apagar a venda.
- Responsividade: larguras 360, 390, 768, 1024 e 1440; sem overflow horizontal da página nos cenários testados. Menu mobile, Escape/foco, movimento reduzido e arraste verificados.
- Recuperação: falha de atualização simulada, mensagem e tentativa posterior; preferências persistentes e logout.
- Mapa MapLibre: canvas com dimensão útil, worker próprio e tiles OSM carregados. Verificação visual no Chrome.
- Auditorias: `npm audit --omit=dev` e `pip-audit -r requirements.lock`: **nenhuma vulnerabilidade conhecida encontrada** na consulta desta data.
- Migração 001 → 002 aplicada à base local. Backup consistente com integridade `ok`, revisão 002, 16 leads e 1 site demonstrativo.

## Limites da entrega

A aplicação foi executada localmente. Railway/domínio HTTPS, persistência do volume após redeploy e Docker não foram executados aqui (Docker indisponível). PostgreSQL não homologado. Segurança revisada em SECURITY-REVIEW.md, com verificações de infraestrutura a cumprir em SECURITY.md e DEPLOY.md.

O build avisa sobre o chunk MapLibre maior que 500 kB: aproximadamente 1 MB minificado / 279 kB gzip, carregado na área de mapa, com worker separado. Sem polling ou jobs de fundo. Métricas reais de memória/custo no Railway ainda precisam ser medidas.

O Radar possui provider desacoplado; a versão atual recomenda Geoapify em produção e mantém OpenStreetMap/Overpass somente como fallback explícito de desenvolvimento. Avaliações Google e atividade recente de redes sociais não são inferidas. Exemplos continuam fictícios. Sites não monitora disponibilidade nem verifica SSL externamente; alertas usam dados cadastrados. Valores mensais de Sites são projeções, separados dos recebimentos efetivos.

## Evidências locais

`artifacts/` contém screenshots desktop/mobile e relatório Playwright; não integra o pacote público de código. O pacote inclui código, testes, locks, migrações e documentação, sem `.env`, banco, credenciais locais ou dependências instaladas.


## Validação do patch do Radar

- Backend: **24 testes aprovados** após o patch. Os cenários novos cobrem duas buscas consecutivas, persistência sem duplicação, empresas homônimas em locais diferentes, resultado vazio, timeout/erro/429 da fonte externa, validação de parâmetros, serialização OSM e adição ao Pipeline.
- Modo produção do backend permanece coberto pelo teste isolado de cookies seguros, headers, origem e documentação privada.
- Frontend alterado foi transpilado/sintaticamente validado com TypeScript em modo `--noCheck`, incluindo `App`, Radar, mapa, API e tipos.
- O bundle Vite não pôde ser recompilado neste ambiente de patch porque o sandbox não resolveu `registry.npmjs.org` (`EAI_AGAIN`) e o ZIP baseline não inclui `node_modules`. O código não adiciona dependências JS e o `package-lock.json` permanece intacto; o build completo deve ser repetido em ambiente com acesso ao registry antes do deploy.
- O acesso real a Nominatim/Overpass também não pôde ser executado pelo sandbox por bloqueio de DNS. O contrato externo foi validado com respostas simuladas de fonte e as URLs/políticas atuais foram conferidas na documentação pública.

## Hotfix Radar / timeout em produção

- Corrigida a consulta sem nicho para não varrer todo `shop`/`amenity`/`office` do raio.
- Adicionado failover entre instâncias públicas Overpass configuráveis.
- Timeout exclusivo da chamada do Radar no frontend elevado para comportar uma segunda tentativa sem afetar as demais APIs.
- `PYTHONPATH=. pytest -q`: 26 testes aprovados após o hotfix.


## Radar Geoapify + autocomplete de localização

- Provider de produção migrado para Geoapify, com chave somente no backend e sem fallback silencioso para Overpass em `APP_ENV=production`.
- Autocomplete de municípios usa catálogo IBGE carregado pelo backend, cache em memória de 24 h e filtro local no frontend; entrada manual continua disponível se o catálogo falhar.
- Suíte Python executada com `TZ=America/Sao_Paulo`: **29/29 testes passaram**, incluindo busca, vazio, erros externos, configuração ausente, persistência/deduplicação, Pipeline, serialização Geoapify e catálogo de cidades.
- TypeScript alterado foi transpilado/sintaticamente validado com `tsc --noCheck` para `App.tsx`, `Radar.tsx` e `types.ts`.
- `npm ci --offline` não pôde concluir porque um pacote não estava no cache local e o sandbox não possui resolução DNS externa; por isso o bundle Vite completo não foi executado neste ambiente. O build real deve ser confirmado pelo Railway após configurar `RADAR_GEOAPIFY_API_KEY`.
- Nenhuma chamada real Geoapify/IBGE foi feita pelo sandbox por bloqueio de DNS. Os contratos externos foram cobertos por testes simulados e conferidos contra a documentação oficial.


## Hotfix Radar / precisão e qualidade dos resultados

- Município selecionado no autocomplete agora é enviado de forma estruturada (`city_name`, estado, UF e ID IBGE).
- Geoapify usa geocodificação estruturada e cruza `place_id` da cidade com o raio da busca.
- O backend revalida distância, país e UF de cada resultado e normaliza a cidade para o município selecionado, evitando vazamento como Recife → João Pessoa.
- Grandes redes conhecidas (ex.: McDonald's, Burger King, Starbucks e equivalentes da lista conservadora) são excluídas da descoberta de oportunidades.
- Busca ampla consulta até 72 candidatos por padrão, prioriza sinais úteis para prospecção, diversifica categorias e retorna até 24 resultados.
- Enriquecimento detalhado foi ampliado para os 12 candidatos de maior prioridade.
- Suíte Python executada com `TZ=America/Sao_Paulo`: **32/32 testes passaram**.
- `npm ci` não concluiu neste sandbox por indisponibilidade/timeout do registry; por isso o bundle Vite completo não foi reexecutado aqui. As alterações TypeScript deste hotfix são restritas ao payload tipado do Radar e ao auto-resolve de município exato.


## MapTiler visual / fallback do Radar

- `/api/radar/map-config` agora expõe somente a chave pública MapTiler e o ID de estilo; a chave server-side do Geoapify continua isolada.
- Com `RADAR_MAPTILER_API_KEY`, o MapLibre usa o Style JSON do MapTiler; o padrão é `dataviz-v4-dark`, adequado a dashboards escuros.
- `RADAR_MAPTILER_STYLE_ID` aceita tanto estilos oficiais quanto o ID de um mapa personalizado criado no MapTiler Cloud.
- Sem chave ou diante de falha de carregamento inicial do estilo MapTiler, o mapa retorna automaticamente ao fallback MapLibre/OpenStreetMap sem interromper lista, detalhes ou Pipeline.
- A política CSP removeu os domínios Google adicionados no patch anterior e liberou somente MapTiler + fallback OSM para a camada cartográfica.
- Pins, seleção, fit de bounds, zoom, recentralização e tela cheia permanecem na UI própria do ScoutLIQ.
- Backend testado após a troca: **34/34 testes passaram** com `TZ=America/Sao_Paulo`.
- Os componentes TypeScript alterados foram validados com `tsc --noCheck --noEmit`. O `npm ci` completo não concluiu neste sandbox por timeout de acesso ao registry, então o bundle Vite final deve ser confirmado pelo build do Railway.

### Importação por link do Google Maps

- O fluxo aceita links HTTPS de `google.com`, `google.com.br`, `maps.google.com`, `maps.app.goo.gl` e `goo.gl`; outros hosts são rejeitados antes de qualquer acesso externo.
- Links encurtados são resolvidos com no máximo 5 redirecionamentos e timeout dedicado. O backend não raspa o HTML do Google como fonte de dados.
- Nome e coordenadas são extraídos da própria URL quando disponíveis; Geoapify é usado apenas como enriquecimento para endereço, cidade, categoria, site, Instagram, telefone e WhatsApp públicos. Campos não confirmados permanecem vazios.
- A prévia não persiste nada. O usuário revisa os campos e só então salva. Leads importados usam `source=google_maps` e deduplicação por `source_id` + identidade composta.
- Testes cobrem parsing, rejeição de host não Google, prévia sem persistência e deduplicação no salvamento.

## Cadastro e autenticação

Cobertura automatizada adicionada para cadastro, bloqueio de login antes da confirmação, confirmação por token, reenvio, recuperação genérica, redefinição de senha, revogação de sessões e token expirado.

## v1.16.0 · Research & Automation 2.0 · parcela 1

- `TZ=America/Recife PYTHONPATH=. pytest -q`: **86 passed**.
- `python -m compileall -q backend migrations tests`: aprovado.
- `alembic heads`: `015 (head)`.
- `Radar.tsx`, `types.ts` e `i18n.ts`: transpilação TypeScript sintática aprovada.
- dicionários EN/ES: nenhuma chave duplicada.
- CSS: chaves balanceadas.
- `npm ci`: não concluiu dentro da janela do ambiente, portanto o build Vite completo não foi marcado como validado.


## v1.17.0 · Research & Automation 2.0 · parcela 2

- Backend: 90 testes Pytest passando em `TZ=America/Recife`.
- Alembic: `016` confirmado como head.
- Python: `compileall` sem erros.
- Frontend alterado: validação sintática via TypeScript `transpileModule` sem diagnósticos.
- CSS: parse validado com `tinycss2`.
- `npm run build`: tentativa realizada; instalação npm ficou incompleta por timeout de rede e o TypeScript reportou apenas type libraries ausentes do `node_modules` parcial antes de analisar o projeto.
- Release deve excluir `node_modules`, `frontend/dist`, bancos, caches e arquivos locais.

## v1.17.1 · Railway TypeScript hotfix

- Corrigida a divergência entre o escopo territorial persistido do Radar e o contrato já usado pela API: `region`, `radius`, `bounds` e `polygon` agora compartilham a mesma fonte de tipo.
- `TZ=America/Recife PYTHONPATH=. pytest -q`: **90 passed** após o hotfix.
- Nenhuma migration nova e nenhuma alteração de banco.
- O `npm ci` deste sandbox voltou a expirar antes de concluir; por isso o build Vite completo continua dependente do build do Railway. O erro TS2322 mostrado no Railway foi removido na origem ao eliminar a união duplicada e reutilizar `RadarSearchResponse["scope"]`.

## v1.18.0 · Research & Automation 2.0 · parcela 3

- `PYTHONPATH=. TZ=America/Recife pytest -q`: **93 passed**.
- `alembic heads`: **017 (head)**.
- `python -m compileall`: sem erros.
- validação sintática de todos os arquivos `frontend/src/**/*.ts(x)` com o compilador TypeScript global: **0 erros sintáticos**.
- `tinycss2` em `frontend/src/styles.css`: **0 erros de parsing**.
- dicionários EN-US/ES: sem chaves duplicadas.
- `npm ci` excedeu o limite do ambiente e deixou dependências externas incompletas; por isso o `npm run build` completo não é marcado como aprovado localmente.

## v1.19.0 · Research & Automation 2.0 · parcela 4

- 97 testes backend passando em `TZ=America/Recife`;
- migration `018` validada sobre banco SQLite isolado de testes;
- campanhas, membros, atribuição de venda e snapshots de desfecho cobertos por testes;
- sinais combinados e uso em condição de automação cobertos por testes;
- TS/TSX alterado validado sintaticamente via `typescript.transpileModule`;
- CSS validado por `tinycss2`, zero erros de parsing;
- EN-US e ES auditados para chaves duplicadas, zero duplicatas;
- o `npm ci` deste ambiente falhou com erro interno do próprio npm (`Exit handler never called!`), portanto o build Vite completo deve ser confirmado no Railway.

## v1.19.1 · Railway TypeScript hotfix

- Corrigido `TS6133` em `src/pages/Campaigns.tsx`: import `Users` de `lucide-react` declarado e não utilizado.
- Varredura adicional com a API do TypeScript não encontrou outros diagnósticos de símbolos não utilizados (`TS6133`, `TS6192`, `TS6196`, `TS6198`) no código-fonte atual.
- Backend: 97/97 testes passando com `TZ=America/Recife`.
- Sem migration nova; Alembic permanece em `018`.
