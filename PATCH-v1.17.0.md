# ScoutLIQ v1.17.0 — Research & Automation 2.0 · Parcela 2/4

## Entregas

1. **Watchlist de empresas + detecção de mudanças**
   - acompanhar/parar de acompanhar diretamente na ficha;
   - reutiliza os snapshots temporais do Scout;
   - registra no histórico mudanças relevantes em reviews, nota, site, contatos e unidades;
   - lista inteligente `Acompanhadas`;
   - não cria evento para repetição sem mudança material.

2. **Empresas semelhantes**
   - ação `Semelhantes` no Radar;
   - tenta descobrir novas empresas do mesmo contexto regional/categoria;
   - ranqueia resultados por nicho, categoria, proximidade, tração pública, presença digital, serviços e estrutura aparente;
   - exibe índice de semelhança sem confundir com probabilidade de venda.

3. **Territórios no mapa**
   - desenhar polígono livre com até 32 pontos;
   - buscar apenas dentro do território;
   - `Buscar nesta área visível`;
   - backend filtra geometricamente os resultados, não apenas visualmente;
   - limite de segurança de 25 km a partir do centro para evitar varreduras acidentais gigantes.

## Banco

Migration `016`: adiciona estado da Watchlist ao lead (`watchlisted`, início, última checagem e último evento). Polígonos e bounds vivem na consulta/busca salva e não criam geometria persistente separada.

## Compatibilidade

Release cumulativo sobre v1.16.0. Para pular versões use o pacote FULL. Patch-only pressupõe v1.16.0.
