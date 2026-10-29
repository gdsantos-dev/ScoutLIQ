# Acessibilidade, desktop/mobile e performance — v1.37

## Verificado localmente

Chrome/Playwright com dados sintéticos. E2E cobrem navegação, modais, selects, campos, ficha, grupos, histórico, gestão, Sites e estados de erro. Viewports incluem 320, 375, 390, 393, 430, 768, 1024, 1440 e 1920 px; o conjunto experience verifica ausência de overflow do documento em oito larguras.

axe WCAG 2 A/AA e 2.1 AA: nenhuma violação nos estados auditados. Evidências salvas em evidence-v137/axe-record.json e axe-mobile.json; os demais audits são asserções dos E2E. Isso não equivale a certificação de todas as rotas e estados possíveis.

Teclado: Tab, setas e Enter no catálogo, Escape, foco de retorno, diálogos aninhados e comandos. Scroll: bloqueio do documento, preservação de posição e contenção interna. Reduced-motion é respeitado. VisualViewport ajusta espaço disponível, mas teclado virtual físico não foi homologado. Inspeção visual das capturas confirmou contraste, hierarquia, nitidez do conteúdo e separação do fundo.

## Medição de performance

Uma rodada local de experience.spec.ts registrou Radar pronto em **1737 ms**, 20 recursos iniciais e mapa carregado somente após solicitar a visualização. Os tempos e recursos completos estão em evidence-v137/performance.json. É uma amostra em máquina de desenvolvimento com fixtures; não representa p95, rede móvel ou latência de provedor real.

Build limpo: bundle inicial aproximadamente 149 kB gzip; MapLibre aproximadamente 279 kB gzip, adiado por import dinâmico, com worker separado. Vite conserva aviso de chunk de mapa acima de 500 kB sem compressão. O aviso não foi ocultado elevando limites. A extração de CSS por superfície reorganiza manutenção, não promete reduzir tamanho.

## Limites

Sem Safari/iOS físicos, leitor de tela humano, touchpad físico, teclado virtual real, medição de taxa de quadros em hardware móvel ou teste de carga distribuída. Os dados coletados não autorizam alegar 60 FPS constantes, Lighthouse 100 ou certificação universal de acessibilidade.
