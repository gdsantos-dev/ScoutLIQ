# ScoutLIQ v1.7.0 — Radar Territory & Results

Base funcional: v1.6.0 (Autonomous Territory Research).

Esta é a parcela 1/4 da primeira fase de evolução do ScoutLIQ. O objetivo foi melhorar descoberta e leitura dos resultados sem misturar ainda prioridade explicada, justificativa comercial ou reforma da ficha do estabelecimento.

## 1. Radar: região inteira ou raio

- A busca deixa de forçar região inteira sempre que uma cidade é reconhecida.
- Novo seletor de área com dois modos:
  - **Região inteira**: usa o limite administrativo quando a fonte consegue resolvê-lo.
  - **Por raio**: força busca circular ao redor do centro resolvido.
- Raios disponíveis: 2, 5, 10, 15 e 25 km.
- O modo e o raio ficam persistidos junto da última busca do usuário.
- O backend recebeu `scope: region | radius` e mantém compatibilidade com buscas antigas, cujo padrão continua sendo `region`.

## 2. Filtros do Radar

Além de país, cidade, situação do site e score, o Radar agora pode filtrar por:

- avaliação mínima;
- quantidade mínima de avaliações;
- presença de algum contato;
- telefone;
- WhatsApp;
- Instagram;
- somente empresas ainda no Radar;
- empresas já no Pipeline.

Também foi adicionada ordenação por score, número de avaliações, melhor avaliação ou nome. O botão de filtros mostra a quantidade de filtros ativos e volta a ficar acessível no mobile.

## 3. Resultados mais ricos

Cada resultado agora mostra, quando disponível:

- categoria e cidade;
- nota e número de avaliações;
- sinais objetivos de presença digital e contato;
- ausência ou problema confirmado de site;
- estágio atual quando a empresa já está no Pipeline;
- score atual com acesso à ficha completa.

A interface ainda não chama isso de prioridade nem tenta explicar a oportunidade. Essas duas camadas ficam reservadas para a parcela seguinte.

## Validação

- 22/22 testes do Radar passaram.
- 60/60 testes backend passaram.
- Novo teste garante que `scope=radius` usa filtro circular mesmo quando existe uma fronteira administrativa resolvida.
- TS/TSX alterado foi transpilado com TypeScript sem erros sintáticos.
- O build npm completo não foi concluído neste ambiente porque a instalação das dependências ficou incompleta; não houve falha de código detectada na transpilação.
