# ScoutLIQ v1.8.0 — Opportunity Qualification

Base funcional: v1.7.0 (Radar Territory & Results).

Esta é a parcela 2/4 da primeira fase de evolução do ScoutLIQ. O objetivo é transformar score e sinais existentes em leitura comercial clara, sem usar julgamento subjetivo ou probabilidade inventada.

## 4. Por que é uma oportunidade

A ficha passa a abrir com um resumo comercial baseado em evidências já existentes no lead e na auditoria.

O bloco pode destacar, quando confirmado:

- ausência de site;
- site com problemas;
- falhas importantes encontradas pela auditoria;
- presença local forte por nota e volume de avaliações;
- Instagram;
- telefone ou WhatsApp.

O texto muda conforme os sinais disponíveis e evita afirmar oportunidade forte quando ainda faltam dados.

## 5. Prioridade explicada

O score continua determinístico e deixa de ser o protagonista visual.

A interface traduz o índice para três faixas operacionais:

- **Alta prioridade**: 70–100;
- **Prioridade média**: 40–69;
- **Baixa prioridade**: abaixo de 40.

A ficha explica que o índice é prioridade, não probabilidade de venda, e mantém cada motivo do score com sua pontuação. A lista do Radar também exibe a prioridade junto ao índice.

## 6. Reforma da ficha da empresa

A ficha foi reorganizada em uma sequência mais útil para prospecção:

1. **Oportunidade** — prioridade, motivo e sinais objetivos;
2. **Empresa** — avaliação, endereço, site e contatos;
3. **Pesquisa web / Auditoria** — validação da presença digital e achados técnicos;
4. **Comercial** — valor potencial, etapa e anotações;
5. **Ações** — pipeline, venda, WhatsApp, edição e exclusão.

A seção Empresa ganhou rótulos explícitos para melhorar leitura rápida. As etapas do Pipeline dentro da ficha também passam a respeitar o idioma ativo.

## Validação

- 60/60 testes backend passaram.
- Nova lógica de oportunidade foi validada manualmente por execução do TypeScript transpilado, incluindo limites 70/69/40/39 e cenários de empresa forte/lead sem dados.
- TS/TSX alterado foi transpilado com TypeScript sem erros sintáticos.
- CSS foi parseado sem erros.
- Dicionários EN-US e ES foram verificados sem chaves duplicadas.
- O build npm completo não pôde ser concluído porque a instalação de dependências sofreu timeout de rede e ficou incompleta; a falha observada foi de tipos/pacotes ausentes, não de sintaxe do código alterado.
