# Acessibilidade e desempenho — v1.36

## Evidência local

- Oito larguras do novo workspace: 320, 375, 390, 430, 768, 1024, 1440 e 1920 px; sem overflow horizontal no cenário Radar. Regressão herdada cobre também 393 px e gestão/formulários/ficha.
- Axe WCAG 2 A/AA e 2.1 AA em navegação/ficha/mobile, além dos checks de busca, inteligência, aprendizado e comunicação: sem violações nos cenários finais.
- Foco, Escape, abas por teclado, seleção customizada, erro/retry, sessão expirada e offline cobertos pela regressão. Reduced-motion por preferência do sistema preservado.
- Navegação compacta usa aria-expanded/aria-controls; etapas usam botões com estado pressionado e áreas hidden, mantendo edição montada. Não são abas falsas nem novos painéis.
- Chromium local, dados sintéticos; nenhum teste com leitor de tela físico, Safari/iOS, Android real ou rede móvel. Axe não certifica acessibilidade completa.

## Carregamento

Um run local do build final: Radar/lista pronto em **1802 ms**, 19 recursos observados antes da abertura do mapa. O teste verifica ausência do chunk OpportunityMap na entrada e sua presença após abrir o mapa. Medida de parede incluindo navegação e espera do seletor; **não é LCP nem benchmark estatístico**. Nenhuma promessa de velocidade em produção.

Vite ainda avisa sobre chunk de mapa maior que 500 kB. A biblioteca cartográfica é herdada; não foi removida ou substituída, e carrega somente quando necessária. Sem novas dependências. A lista mantém expansão progressiva e mapa mantém limite de marcadores existente.

Dados brutos: artifacts/experience/performance.json, build-v136-final.txt, experience/after/viewports.json e axe-record.json/axe-mobile.json. O orçamento de provedores continua no backend; mudanças de layout não eliminam custos ou limites configurados.
