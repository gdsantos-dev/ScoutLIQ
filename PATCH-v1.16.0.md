# ScoutLIQ v1.16.0 — Research & Automation 2.0 · Parcela 1/4

Primeira parcela da nova fase de pesquisa e automação.

## 1. Pesquisa em linguagem natural

- novo interpretador determinístico para PT/EN/ES;
- transforma pedidos como `dentistas em Recife sem site, 100+ avaliações e WhatsApp` em critérios estruturados;
- os critérios ficam visíveis antes da busca;
- a interpretação nunca executa filtros ocultos nem inventa localização ausente;
- suporta nicho, região, raio, avaliações, nota, contato, score, confiança, timing e fit por serviço.

## 2. Pesquisa por problema/oportunidade

- filtros baseados diretamente no diagnóstico da Score Engine 2.0;
- sem site próprio;
- site com problemas;
- ausência verificada de agendamento/reserva;
- ausência verificada de cardápio, catálogo ou e-commerce;
- presença digital fraca;
- gap competitivo local;
- filtros adicionais por Confidence Score, Timing e fit de serviço.

Critérios que dependem de auditoria só consideram problemas efetivamente verificados. Dado desconhecido não vira problema por inferência.

## 3. Monitoramento de buscas salvas

- uma busca salva pode ser monitorada diariamente ou semanalmente;
- o snapshot de resultados considera também os filtros de oportunidade, não só cidade/nicho;
- novas correspondências continuam alimentando `last_new_count`;
- execução atrasada é retomada de forma oportunística quando o Radar estiver em uso;
- no máximo quatro monitores vencidos são executados automaticamente por abertura do Radar para respeitar limite do provedor;
- estrutura já deixa `next_monitor_at` persistido para integração futura com worker/cron do motor de automações.

## Dados e migração

- Alembic `015`;
- `radar_saved_searches` passa a guardar estado, frequência e agenda do monitor;
- exportação de dados: schema v10.

## Validação

- 86 testes backend aprovados no fuso operacional `America/Recife`;
- Alembic `015` é o head;
- Python compileall aprovado;
- TS/TSX alterado passou por transpilação sintática;
- CSS com chaves balanceadas.

O build Vite completo não foi carimbado localmente porque o `npm ci` não concluiu no ambiente disponível.
