# ScoutLIQ v1.15.0 — Score Engine 2.0 · Parcela 5/5

Fechamento da Score Engine 2.0 com duas leituras auxiliares e independentes do score principal.

## 1. Estrutura comercial aparente

- novo indicador de 0–100 baseado apenas em sinais observáveis;
- quatro componentes: tração pública, estrutura operacional, maturidade digital e acesso comercial;
- pode considerar volume/nota de avaliações, posição competitiva local, múltiplas unidades detectadas, domínio próprio, analytics, capacidades digitais, Instagram ativo e canais de contato;
- inclui confiança própria de cobertura;
- não estima faturamento, patrimônio, poder de compra ou capacidade financeira.

## 2. Timing comercial

- novo indicador de 0–100 separado do score de oportunidade e do fit por serviço;
- usa mudanças observadas entre varreduras/reanálises e pressão competitiva atual;
- crescimento relevante de avaliações, piora ou desaparecimento do site, novos contatos e nova unidade detectada podem elevar a prioridade temporal;
- site recém-confirmado ou presença web melhorada podem reduzir o timing;
- eventos recentes expiram do cálculo para evitar urgência eterna.

## 3. Observação temporal

- migration `014` adiciona `commercial_signal_json` e `commercial_signal_analyzed_at` ao lead;
- o Radar atualiza avaliações/nota quando a fonte retorna dados mais recentes e preenche canais novos sem sobrescrever dados já existentes;
- marcas com mesmo nome normalizado, categoria e país podem gerar sinal de múltiplas unidades;
- pesquisa web e auditoria profunda atualizam a linha do tempo de sinais quando a presença web muda;
- edições manuais redefinem a linha-base sem inventar eventos externos;
- exportação passa para `schema_version: 9` e inclui `commercial_signals`.

## 4. Interface

A ficha da oportunidade passa a mostrar:

- Estrutura comercial aparente;
- nível e score;
- principais sinais observáveis;
- Timing comercial;
- principais sinais que justificam priorizar ou não a abordagem agora.

As duas leituras deixam explícito que não representam chance de fechamento ou capacidade financeira.

## 5. Validação

- 82 testes backend;
- Alembic `014` como head;
- Python compilado sem erros;
- TS/TSX alterado validado sintaticamente;
- CSS sem erros de parsing;
- dicionários EN/ES sem chaves duplicadas.

O build Vite completo não foi validado localmente porque a instalação das dependências npm ficou incompleta no ambiente de execução.
