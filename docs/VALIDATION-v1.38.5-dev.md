# Validação — ScoutLIQ v1.38.5-dev

## Resultado

Implementado e testado localmente sobre a v1.38.4-dev integrada e verificada contra o FULL de SHA256 `bdf663153db126da40474ac7001cd6a811ffdd95fbdc8d95dd64f0be77e1360e`. Designação **dev**, sem deploy, banco de produção, comunicação comercial real ou consumo de cotas reais de provedores.

| Verificação | Resultado final |
| --- | --- |
| Backend completo | 514 aprovados; dois avisos de depreciação de bibliotecas de teste |
| Frontend unitário | 24 aprovados, 7 arquivos |
| E2E | 72 aprovados, 16 suítes |
| TypeScript aplicação/E2E | Aprovados |
| Vite | Aprovado; aviso conhecido de chunk de mapa maior que 500 kB |
| Migração 032 | Preservação de registros 031, integridade/FKs e downgrade protegido aprovados |
| Arquivos preservados | 49 byte a byte, incluindo 31 migrações anteriores |

O total backend inclui 38 cenários novos de acompanhamento/migração sobre os 476 da base. Rodadas focadas e repetidas não foram somadas. Os E2E incluem 68 cenários históricos, dois da Fila Comercial v1.38.4 e dois novos desktop/mobile.

## Cobertura funcional

Sem contato prévio; contato inválido; rascunho sem aprovação; conteúdo aprovado sem envio; queued/executing/uncertain; aceitação técnica com e sem recibo; entrega desconhecida e evento sintético de confirmação; interesse, pedido de informações, objeção, recusa, opt-out, resposta automática/ambígua; associação errada; ação vencida/futura; fuso do usuário; intervalo configurável; follow-up sem contato e duplicado; atividade manual idempotente com data/proveniência; lotes parciais; duas prévias concorrentes; alteração de resposta/configuração antes de confirmar; ação humana protegida; isolamento; pausa, retomada, conclusão persistente após reabrir conexão; rollback por interrupção e retry sem duplicação; nenhuma outbox criada pelo acompanhamento.

O teste da sincronização prova que resposta nova não substitui `next_action` e data já preenchidas. A associação original por conta/thread/referência/destinatário e o bloqueio de recusas permanecem cobertos pela regressão canônica. Entrega foi testada com evento sintético; não há homologação de recibo de entrega Gmail.

Desktop: atividade manual, prévia parcialmente elegível, follow-up canônico, editor e ausência de outbox. Mobile: consentimento para substituir ação, pausa/retomada, intervalo persistido, reload, reflow 390/320 e Axe no componente. Capturas inspecionadas visualmente; os testes usam Chrome local, não aparelhos físicos.

## Volume, custos e recuperação

Teste canônico com 1.000 empresas: quatro blocos de indexação, 15 consultas na página aquecida de 50 e 0.109 s medidos localmente. O novo índice operacional também foi testado com 301 empresas, blocos de 250/51, paginação sem sobreposição e menos de 20 consultas na leitura aquecida. As medidas não são SLA de produção.

`test_commercial_volume.py` cria sua pasta de saída automaticamente. A importação da aplicação sem dist também foi corrigida para permitir testes após extração limpa. O recibo externo `CLEAN-INSTALL-VALIDATION.json` registra a verificação adicional no FULL final extraído, sem `artifacts/`, `dist` ou `node_modules` preparados previamente.

Leitura local, sem IA paga ou chamadas a provedores. Não há worker novo, habilitação de sync ou campanhas. Prévia/confirmacão, savepoints e idempotência reutilizam CommercialOperation; criação reutiliza OutreachDraft. A trava curta da comunicação protege a confirmação contra alterações concorrentes de execução/respostas. Preferências persistem; erro de infraestrutura reverte a transação e permite retry.

## Segurança e compatibilidade

Autenticação/CSRF existentes; isolamento por usuário em Leads, preferências, operações, rascunhos, contas, mensagens e eventos; DTOs fechados e campos permitidos; limite 50; rate limiting; queries ORM parametrizadas; pesquisa textual escapada; texto externo renderizado como texto React; nenhum HTML executável, nova URL remota ou upload. IDs nunca substituem autorização. Metadados de atividade são construídos no backend, sem aceitar recibos arbitrários de provedor pelo DTO.

Não há alteração de privilégios, estágio, consentimento ou RecipientPolicy em massa. Opt-out/recusa manual em resposta suspende o Lead e pausa rascunhos; retomar acompanhamento não desbloqueia contato. Preparação, aprovação, condição de contato, autorização por mensagem e execução externa permanecem separados. `communication.py`, `outreach_intelligence.py`, `opportunity_workflow.py`, automações, worker, Score, investigação e absorção protegidos permanecem idênticos à base. A guarda de `communication_replies.py` só preserva ação existente; não amplia leitura nem altera associação.

Não foram adicionadas dependências. NoSQL, uploads, novos webhooks, novos endpoints administrativos e novos destinos de rede não se aplicam a esta fatia. Configurações de autenticação, cookies, CORS e cabeçalhos não foram ampliadas. Auditoria atualizada de dependências e HTTPS do ambiente-alvo continua necessária antes de publicação. Pacotes excluem runtime, .env reais, bancos, caches, dependências e dist.

## Estado da entrega e limites

- **Implementado/testado localmente:** planejador, integração Pipeline/Radar, registros manuais, ações supervisionadas, persistência, migração e testes listados.
- **Homologado externamente:** nenhum componente novo foi assim classificado. PostgreSQL do ambiente-alvo, Safari/dispositivos físicos, credenciais e provedores reais, HTTPS e qualidade comercial com casos ORLIQ continuam pendentes.
- **Limites implementados:** índice inicial parcial em blocos de 250; cache temporal até cinco minutos e virada do dia; eventos ORM invalidam imediatamente. Atividades são lidas em janela de até duas por tipo, com interpretação conservadora. O histórico completo continua acessível. O compositor usa templates existentes; conteúdo contextual detalhado exige revisão no editor.
- **Bloqueios técnicos locais:** nenhum nas execuções finais registradas. Contatos bloqueados e contextos insuficientes são recusas funcionais esperadas, não falhas de teste.
- **Sem comprovação comercial real:** prioridade operacional e testes sintéticos não provam aumento de respostas, conversão ou consentimento.

## Artefatos

[Fluxo e regras](FOLLOWUP-v1.38.5-dev.md), [instalação/migração](INSTALL-v1.38.5-dev.md), [changelog](CHANGELOG-v1.38.5-dev.md), [arquivos](CHANGED-FILES-v1.38.5-dev.md) e [checkpoint](CHECKPOINT-v1.38.5-dev.md).

Evidências: [desktop](qa-v1.38.5-dev/followup-desktop.png), [prévia](qa-v1.38.5-dev/followup-preview-desktop.png), [390 px](qa-v1.38.5-dev/followup-390.png), [320 px](qa-v1.38.5-dev/followup-320.png), [recibo estruturado](qa-v1.38.5-dev/VALIDATION.json). Logs finais estão na mesma pasta; podem mostrar caminhos locais de teste, sem credenciais reais.

O recibo externo `release/PACKAGE-VALIDATION.json` registra testes efetivos de hashes, CRC/manifestos, dry-run sem escrita, recusa de customização local, PATCH equivalente ao FULL, preservação de runtime sintético, recusa de reaplicação e rollback de fontes. Recibos internos verificam fontes; externos verificam os ZIPs finais.
