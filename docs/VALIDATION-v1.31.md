# Validação — ScoutLIQ 1.31.0

Execução local em Windows, 10/10/2026, com SQLite e dados sintéticos. Base exclusiva: FULL 1.30.0, SHA256 `9e766cc9ac6b15c7d6b0916c5560aa4bca846f50ad61689d1ea2e15aae5d6897`. Candidata isolada; base e instalação histórica preservadas.

## Resultados finais

| Verificação | Resultado | Evidência local em artifacts/ |
| --- | --- | --- |
| Backend completo, incluindo migrações | **141 passaram**, 2 avisos de depreciação; 92,60 s | pytest-v131-confirm.txt |
| Frontend unitário | **22 passaram** | vitest-v131-final.txt |
| Typecheck E2E | Passou, incluindo o teste adicional de conflito | typecheck-v131-final.txt |
| Build de produção | Passou; aviso de chunk grande do MapLibre mantido | build-v131-final.txt |
| E2E histórico completo | **25 de 25 passaram**, sem skip ou redução de regras axe | e2e-v131-final.txt |
| Ficha operacional + worker após fechar página | **4 de 4 passaram** na mesma rodada histórica; total 29 em 11,1 min | e2e-v131-final.txt |
| Edição concorrente e recuperação explícita | **1 passou**; texto local preservado e salvo após reconciliação | conflict-v131.txt |
| npm audit | **0 alertas conhecidos** | npm-audit-v131.json |
| pip-audit do lock completo | **0 alertas conhecidos**, 24 pacotes; --disable-pip --no-deps | pip-audit-v131.json |
| Comparação dos motores com a base | scoring.py, research.py, providers.py e automation.py idênticos por hash | candidate-source-review.json |

São **30 cenários E2E únicos**: 25 históricos e 5 operacionais. O teste de conflito foi acrescentado depois da rodada de 29 e executado separadamente sobre o mesmo build. Não somar reexecuções como cobertura adicional. Os avisos Python são de APIs depreciadas de Starlette/httpx e anyio, não falhas. Auditorias refletem o catálogo consultado, não garantia de ausência de vulnerabilidades desconhecidas.

## Falhas encontradas e corrigidas

- Contraste do contador em Ações: cor corrigida, axe aguarda animações finitas antes de medir; limites de contraste preservados.
- Seletor histórico de cabeçalho do Radar: atualizado para o componente real; navegação usa nomes acessíveis atuais de Negociações/Entregas.
- Overflow mobile em resumos de Campanhas/Automações e texto de Sobre: margens e distribuição corrigidas. Resumos quebram linha, sem área de rolagem inacessível. Lista horizontal de campanhas ficou contida no viewport de 320 px.
- Estado vazio de Sites tinha duas instâncias DOM, uma oculta: teste usa heading acessível, sem selecionar arbitrariamente o primeiro elemento.
- Monitor ativo passou a agendar trabalho no servidor: cenário histórico verifica persistência/agendamento e ausência de execução pelo browser; depois desativa monitor e verifica busca manual e isolamento de resultados.
- Nova revisão de evidência introduziu summary aninhado: seletor aponta ao summary direto.
- Troca de abas recriava o contêiner da ficha e apagava edição local: identidade do contêiner agora está vinculada ao lead. Cenário de persistência comprova a correção.
- Conflito de edição recarrega estado do servidor sem apagar o texto local; operador pode comparar e manter sua edição sobre a versão atual explicitamente. Cenário adicional comprova o salvamento posterior.
- Contradição quando o limite de 200 evidências já foi atingido: evidência anterior deixa de ser utilizável e o histórico registra a nova observação, mesmo sem criar mais uma linha.

Uma rodada backend anterior teve 140 aprovações e um subprocesso Alembic encerrado pelo Windows com código 3221227274, sem stderr, durante pressão de memória. Os dois testes de migração passaram isoladamente; depois a suíte completa passou com 141. Nenhum teste foi removido, marcado skip ou teve asserção afrouxada para absorver a falha.

## Cenários de aceitação

A/B: reconciliação equivalente/divergente, falha de coleta, preservação de histórico, cobertura por área e recomendação contextual sem alterar o score. C: fatos estruturados localizados e bloqueio de observações livres EN/ES sem tradução revisada. D: preparação idempotente, edição, aprovação de conteúdo e invalidação por mudanças, expiração e política; sem autorização automática de envio. E: opt-out do mesmo destinatário em outro lead da mesma conta, sem fusão por domínio/nome/telefone parcial.

F: teste fecha de fato a página antes de iniciar um subprocesso worker com provedor controlado. Reabre o navegador e confirma **3/3 itens concluídos**, lote completed e evidência persistida. Prova em background-browser-proof.json. Nenhuma consulta externa foi necessária à fixture.

G: claims simultâneos têm um vencedor; lease expirado permite recuperação e impede commit antigo; pausa/cancelamento em trânsito descartam resultado; retry/backoff e orçamento persistem; monitor reutiliza RadarSavedSearch e recusa autoridade concorrente do browser. A recuperação simula interrupção e expiração do claim; não é homologação de supervisor ou teste de falha de energia.

H/I: vazio, erro 503, retry, teclado, Escape, movimento reduzido, aprovação sem envio fictício, edição local entre abas e conflito com outra sessão. Fluxos históricos abrangem CRM, contatos manuais, venda, pagamento, despesas, exportação, Sites, campanhas, automações, idiomas, moeda, pesquisa e autenticação.

## Interface e acessibilidade

Playwright/Chrome desktop com viewports históricos de 320, 375, 390, 393, 430, 768 e 1920 px; ficha também em 1024 e 1440 px. Asserções de overflow preservadas. Axe WCAG2 A/AA e WCAG2.1 AA nas superfícies cobertas pela suíte, sem desabilitar regras. Capturas finais workflow-overview.png, workflow-desktop.png e workflow-mobile.png inspecionadas visualmente. Não equivale a auditoria manual integral de WCAG, leitor de tela, Safari ou dispositivos físicos.

## Desempenho observado

12 leituras locais de /workflow, com uma evidência e um rascunho: mediana aproximada **58,0 ms**, p95 observado **83,5 ms**. Amostra pequena em máquina com outros processos ativos; não é teste de carga, provedor externo, rede pública ou FPS. Não há afirmação de ganho comparativo contra a v1.30.

Build: ContextPanel 53,22 kB (15,53 kB gzip); entrada principal 438,63 kB (139,66 kB gzip); MapLibre 1.024,34 kB (279,23 kB gzip). Mapa continua em chunk separado e mantém o aviso acima de 500 kB. Não se aumentou o limite para ocultar o aviso.

## Pacotes e reprodução

```powershell
python scripts/build_release.py --base <FULL-exato-v1.30.0.zip>
python scripts/verify_release.py --base <FULL-exato-v1.30.0.zip>
```

O verificador usa cópias descartáveis para conferir todos os hashes, equivalência PATCH → FULL, preflight sem escrita, backup dos fontes, preservação de .env/banco/cache local, recusa de reaplicação e recusa de conflito sem escrita. O resultado desta execução fica em artifacts/release-validation.json; hashes finais em release/SHA256SUMS.txt e lista exata em release/CHANGED-FILES.json. RELEASE-MANIFEST.json acompanha o FULL; PATCH-MANIFEST.json acompanha o PATCH.

ZIPs incluem fontes, documentação e testes reproduzíveis. Excluem dados reais, bancos, .env, dist, node_modules, logs, auth E2E, capturas e traces. Evidências locais de navegador podem conter cookies sintéticos e não são destinadas à publicação.

## Estado e limitações

**Implementado e testado localmente:** evidência contextual, reconciliação, diagnóstico, próxima ação, estratégias determinísticas PT/EN/ES, conteúdo aprovado separado de condição do canal, opt-out por destinatário, edição preservada, worker sobre filas existentes, migração 020 e regressão completa descrita acima.

**Limites deliberados:** um executor global por SQLite; orçamento por tarefas/tentativas, não teto financeiro/HTTP; leitura externa pode repetir após crash; retentativas não significam exactly-once de rede. O worker precisa estar ativo e compartilhar banco/volume com web. A política de destinatário não presume identidade entre e-mail e telefone; registre os canais abrangidos pelo pedido.

**Não implementado nesta etapa:** OAuth Gmail, envio oficial WhatsApp Business/Gmail, webhooks de resposta, outbox de comunicação, verificação automática de consentimento/mercado, sequências de envio e aprovação em lote. Não basta fornecer credenciais para habilitar envio. Preparação é determinística, sem LLM.

**Não homologado:** produção/Railway/Docker, HTTPS público, PostgreSQL, provedores reais, operação 24/7, aparelhos físicos e políticas jurídicas por mercado. Nenhuma mensagem comercial real foi enviada e nenhum deploy foi realizado. Etapa oficial detalhada em SECURITY-GATE-v1.31.md; instalação e worker em INSTALL-v1.31.md; contratos em CONTRACTS-v1.31.md.
