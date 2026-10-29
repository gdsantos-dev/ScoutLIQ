# Validação — ScoutLIQ v1.38.4-dev

## Resultado e escopo

Implementado e testado localmente sobre o FULL v1.38.3-dev verificado. A entrega permanece **dev**, sem homologação externa, deploy, alteração de banco de produção, envio comercial ou consumo de cotas reais de provedores. Casos e destinatários dos testes são sintéticos.

| Verificação | Resultado |
| --- | --- |
| Regressão backend | 475 aprovados |
| Volume adicional | 1 aprovado; 1.000 empresas |
| Total de testes backend distintos | 476 |
| Frontend unitário | 24 aprovados em 7 arquivos |
| E2E | 70 aprovados em 15 suítes |
| TypeScript aplicação e E2E | Aprovados |
| Build Vite | Aprovado; aviso de chunk de mapa maior que 500 kB |
| Migração | Upgrade 030→031 preserva registros; downgrade protege decisões/recibos |
| Arquivos protegidos | 46 idênticos à base, incluindo as 30 migrações anteriores |

As 14 suítes históricas cobrem busca geral/unificada, mapa, busca inteligente, absorção, autonomia, experiência, workflow, absorção inteligente, redesign existente, aprendizado, inteligência, comunicação e investigação. A suíte comercial adiciona desktop e mobile. Rodadas focadas sobrepostas não foram somadas ao total.

## Provas do novo fluxo

- Fila com classificação canônica, dados incompletos e score alto sem evidência: ausência de fatos confirmados exige abordagem inicial. Contato ausente não rebaixa a avaliação comercial.
- Serviços derivados de evidências confirmadas e vigentes; Sistemas/Social dependem de observação humana específica. Fatos, inferências e desconhecidos separados.
- Lotes até 50, prévia persistente, confirmação, elegibilidade individual, resultado parcial, motivos, reabertura e histórico. Lead, estágio, score e políticas preservados.
- Conflitos de versão/contexto e duas confirmações concorrentes; repetição idempotente; erro inesperado provoca rollback e permite retomada segura. Registro estrangeiro não revela dados.
- Destinatários ausentes/inválidos/bloqueados, política alterada após prévia, evidência alterada e rascunho editado após aprovação. Compositor canônico e aprovação individual reutilizados.
- PT-BR, EN-US e ES; e-mail e WhatsApp explícito; nenhuma criação de mensagem/outbox pela operação comercial.
- Seleção mantida entre filtros e reload na mesma aba; triagem/reabertura; rascunhos com elegibilidade parcial; editor existente, acessibilidade automatizada e reflow a 390/320 px.

Durante a validação foram corrigidos o clique prematuro em selecionar página durante carregamento e o fechamento por Escape do resultado enquanto a atualização da fila continuava. A suíte comercial final passou após as correções. Ajustes de fixtures respeitaram a classificação canônica e a validação de WhatsApp já existentes. Não há falha conhecida restante nas execuções finais registradas.

## Volume e consumo

SQLite local, 1.000 empresas sintéticas: quatro blocos de indexação de até 250; pendentes 750/500/250/0. Indexação fria 1.953 s; página aquecida de 50 registros 0.172 s e 15 consultas. Número de consultas limitado, sem buscar todos os corpos de rascunhos/evidências. Resultados medidos neste ambiente; não são promessa de latência em produção. A visualização não consulta provedores nem exige IA paga.

## Segurança e preservação

Autenticação e CSRF existentes preservados; consultas por proprietário em todas as operações/IDs; DTOs fechados e limite de lote; ORM/parametrização e escape de filtros; rate limiting da fila/prévia/confirmação; idempotência persistente e revalidação de versões. Dados externos são texto, sem interpretação como instruções executáveis. A UI usa renderização React, sem HTML externo. Nenhum campo de privilégio, estágio ou política é atribuído em massa.

`communication.py`, `outreach_intelligence.py`, worker, investigação, pesquisa, Score, Absorção e componentes canônicos protegidos permanecem byte a byte iguais à base. `opportunity_workflow.py` somente extrai o serviço de criação para compartilhamento com a operação individual, coberto pela regressão. Não foi introduzido adapter, credencial, upload, webhook, NoSQL ou novo endpoint administrativo. Configurações existentes de CORS, cookies, cabeçalhos e autenticação não foram ampliadas. Não houve nova dependência; auditoria atual de CVEs e configurações HTTPS do ambiente-alvo permanece necessária antes de publicação.

Pacotes somente de fontes: excluem .env reais, bancos, caches, dependências, dist e runtime. O recibo de distribuição `release/PACKAGE-VALIDATION.json` registra a conferência efetiva de hashes, dry-run sem escrita, rejeição de customização local, PATCH equivalente ao FULL, preservação de runtime sintético, recusa de reaplicação e reversão de fontes. O verificador independente confere manifestos e recibos internos do FULL extraído.

## Limitações e homologação

- **Implementado/testado localmente:** fila, resumos determinísticos, triagem persistente, rascunhos, recuperação, migração, regressão e empacotamento verificável.
- **Comportamento limitado documentado:** indexação inicial em blocos de 250; lista provisória enquanto houver pendentes. Revalidação temporal até cinco minutos; alterações pela aplicação invalidam o cache imediatamente. Escritas SQL externas não disparam os eventos ORM. Seleção permanece na mesma aba; decisões e operações persistem no banco.
- **Fora da homologação local:** PostgreSQL do ambiente-alvo, deploy HTTPS, Safari/dispositivos físicos, integrações reais e qualidade comercial medida com casos humanos ORLIQ. Nenhuma alegação de ganho de conversão real.
- **Comunicação:** apenas preparação. Conteúdo exige revisão individual; condição de contato e autorização por mensagem continuam separadas. Dispatch não foi desbloqueado e nenhum envio em lote foi implementado.
- **Bloqueios técnicos locais:** nenhum nas verificações finais. Homologação externa depende do ambiente e dos acessos correspondentes; não foi simulada.

## Evidências e reprodução

Logs finais, métricas e recibo estruturado em [qa-v1.38.4-dev](qa-v1.38.4-dev/VALIDATION.json). Capturas: [desktop](qa-v1.38.4-dev/commercial-queue-desktop.png), [editor canônico](qa-v1.38.4-dev/commercial-draft-desktop.png), [390 px](qa-v1.38.4-dev/commercial-queue-390.png), [320 px](qa-v1.38.4-dev/commercial-queue-320.png). Os logs podem conter caminhos locais do ambiente de teste; não contêm credenciais reais.

Procedimentos em [INSTALL-v1.38.4-dev.md](INSTALL-v1.38.4-dev.md), fluxo em [COMMERCIAL-OPERATIONS-v1.38.4-dev.md](COMMERCIAL-OPERATIONS-v1.38.4-dev.md) e continuidade em [CHECKPOINT-v1.38.4-dev.md](CHECKPOINT-v1.38.4-dev.md).
