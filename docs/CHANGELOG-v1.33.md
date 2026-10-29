# 1.33.0 — checkpoint funcional P0.1

## Implementado

Supervisor web/worker no mesmo serviço/volume, heartbeat independente, readiness, encerramento de processos irmãos e recuperação por lease. Rotinas explícitas de prospecção e atualização de pesquisa sobre RadarSavedSearch, SmartSearch e ResearchBatch. Critérios congelados, frequência, cotas, histórico, pausa/cancelamento, supressão de oportunidades repetidas e cooldown. Ledger de tarefas/operações e exposição honesta de custo desconhecido. Migração 022 e seção integrada à página Automações, sem redesign.

## Estado por frente

| Frente | Estado |
|---|---|
| P0.1 worker, recorrência, limites e recuperação | Implementado; validação local detalhada no relatório |
| Docker/Railway, volume e operação 24/7 | Implementado no código/configuração; não homologado externamente |
| P0.2 interpretação híbrida, planejador multifonte, novo enriquecimento | Não iniciado nesta fatia; preservado comportamento determinístico 1.32 |
| P0.3 importação de casos humanos e métricas supervisionadas | Não iniciado; fixture 1.32 não é conjunto real ORLIQ |
| P0.4 Gmail, OAuth, tokens, outbox, respostas e CRM | Não iniciado; não habilitado por configuração |
| P1 WhatsApp Business | Não iniciado; integração oficial futura |
| Central completa de decisões/conversas | Parcial: resultados/interrupções das rotinas disponíveis; respostas e aprovações multicanal não |
| Qualidade e consolidação desta fatia | Implementado/testado localmente; ver relatório e Security Gate |
| Homologado externamente | Nenhum recurso novo |

## Guia de integrações e pendências externas

Geoapify/OSM/Brave usam os adapters e variáveis existentes; esta entrega não muda contratos de dados, fontes nem políticas de uso. Operador deve validar cobertura e cotas da sua conta antes de ativar rotinas reais. Não foi feita coleta comercial real para QA. Gmail e WhatsApp não possuem adapter neste pacote; conexão do ChatGPT não autoriza a conta ScoutLIQ. SMTP/Brevo transacional continua separado e não foi convertido em transporte comercial.

Futuro Gmail: configurar app OAuth oficial, escopos mínimos, armazenamento cifrado/revogável de tokens no backend, identidade e política do destinatário, aprovação vinculada a conteúdo/canal/contexto, outbox idempotente, reconciliação e respostas; testar adapter controlado antes de homologação autorizada. WhatsApp deve reutilizar essa infraestrutura com assinatura de webhook, templates/janela/consentimento. Esses itens são plano, não integração implementada nem promessa de envio.

## Próxima ação exata

Iniciar P0.2 na pasta consolidada 1.33: preservar o contrato `Intent` e criar interpretação opcional validada por schema, com provedor/modelo/orçamento explícitos e fallback determinístico identificável. Antes de adicionar fontes, documentar capacidade, território, termos/custos e proveniência dos adapters oficiais disponíveis. Completar uma fatia de intenção → plano limitado → enriquecimento → evidência → mesma prioridade 3.0, com testes controlados e rastreabilidade. Não alterar pesos automaticamente.

Prompt 3: reconstrução visual/navegação integral continua não iniciada. Os novos contratos podem ser reutilizados nessa etapa; não iniciar redesign antes dela. A medição local demonstra execução com navegador fechado, contagem e recuperação; não demonstra redução de tempo comercial numa amostra real da ORLIQ.
