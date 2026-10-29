# ScoutLIQ 1.31 — inteligência aplicada e execução persistente

## Base e invariantes

Base exclusiva: `ScoutLIQ-v1.30.0-full-source.zip`, SHA256 `9e766cc9ac6b15c7d6b0916c5560aa4bca846f50ad61689d1ea2e15aae5d6897`. O ZIP foi extraído em uma pasta nova. A v1.20 histórica e a entrega v1.30 permanecem separadas. React 19, Vite, FastAPI, SQLAlchemy, Alembic e SQLite foram preservados. A revisão anterior era 019; esta entrega acrescenta 020.

Continuam únicos: Lead (oportunidade), LeadResearch (última investigação), OpportunityEvidence (afirmações), OutreachDraft (mensagens), LeadActivity (histórico), Opportunity Score (prioridade), ResearchBatch/ResearchBatchItem (lotes) e RadarSavedSearch (monitores). `ResearchExecutor` é um registro singleton de exclusão mútua e orçamento, não uma segunda fila.

## Contratos verificados e mudanças

| v1.30 | v1.31 |
| --- | --- |
| Pesquisa com timestamp novo tornava todo snapshot anterior vencido | Falha de coleta preserva fatos anteriores; expiração depende da categoria. Resultado equivalente atualiza a mesma evidência; resultado diferente guarda o anterior como substituído e cria vínculo auditável |
| Checks negativos viravam “requer verificação” | Predicados explícitos correspondem ao analisador HTML; escopo é somente página/instante, classificação inicial provável |
| Revisão manual confundida com comprovação independente | Origem, escopo, categoria, última verificação, justificativa e versão do analisador aparecem na evidência |
| Cobertura era confirmadas/total | Seis áreas declaradas de investigação; confiabilidade qualitativa separada do score existente, sem percentual inventado |
| Próxima ação era uma sequência curta de condições | Serviço `decide` centraliza justificativa, comando, evidências, pré-condições, bloqueios, estado e data |
| “Preparar proposta” abria histórico | “Registrar próxima atividade” abre o histórico com anotação selecionada; não promete gerador de propostas |
| Modelos EN/ES incluíam afirmações em português | Vocabulário estruturado localizado; afirmações livres exigem tradução revisada. Falta de tradução bloqueia a preparação |
| Referência textual era tratada como autorização | Aprovação de conteúdo e condição de envio são estados separados; declaração nunca ativa envio |
| Bloqueio restrito ao lead | Política por usuário/canal/destinatário normalizado, compartilhada entre leads. E-mail não perde pontos/sufixo +; telefone exige código internacional, sem fusão por últimos dígitos |
| Navegador executava `/step` | Modo padrão worker; browser consulta o progresso. `/step` retorna 409 nesse modo |

## Evidências e diagnóstico

O catálogo mapeia HTTPS, viewport, título, description, dados estruturados, canal de contato e duração de resposta aos predicados reais de `research.py`. Um critério não atendido não é uma conclusão de que todo o site está quebrado. Revisões e reconciliações usam LeadActivity, inclusive o texto anterior quando necessário.

Validades máximas automáticas: desempenho 3 dias; segurança 7; contato 14; mobile/descoberta/conteúdo 30. Observação manual padrão: até 14 dias, limitada pela categoria. Revisar classificação não prorroga a data de validade de uma coleta antiga. Traduções são declarações revisadas do operador, não certificação linguística automática. Não há LLM ou custo obrigatório de IA.

O diagnóstico usa fatos revisados atuais, informa divergências e sugere melhorias pontuais por categoria. A prioridade, fatores e dimensões comerciais continuam vindo do motor original. A contagem de áreas investigadas não representa qualidade completa de auditoria nem probabilidade de venda.

## Rascunhos e política de contato

As estratégias determinísticas têm pré-condições: apresentação inicial não exige apontar um defeito; oportunidade verificada exige evidência pertinente; retomada exige contato registrado; resposta exige retorno registrado. O conteúdo original e traduções revisadas ficam na evidência. O editor mostra destinatário, assunto, corpo, caracteres, prévia, versão salva e alterações pendentes.

O hash de aprovação vincula conteúdo, canal, idioma, destinatário, versões de evidências/lead/política e expiração. Alterações relevantes invalidam sua utilização. A aprovação de texto sem condição declarada é permitida, mas a elegibilidade continua indeterminada. Uma condição preenchida fica pendente de verificação de mercado/provedor. Opt-out impede preparação e aprovação para o destinatário equivalente em outros leads. Outros contatos do mesmo domínio não são fundidos.

E-mail e telefone não são associados automaticamente a uma pessoa. Um pedido referente a ambos deve ser registrado para ambos, ou como recusa de toda a oportunidade quando esse for o escopo solicitado. O registro não infere relação de identidade a partir de nome, empresa ou sufixo de telefone.

O dispatch continua falhando fechado. Não existe adapter de envio, OAuth, webhooks de resposta ou entrega real nesta versão. Estados de política nunca substituem as verificações desses componentes futuros.

## Worker e recuperação

`python -m backend.research_worker` opera sobre as filas existentes. Um UPDATE condicional adquire o registro singleton antes do claim da tarefa. A transação persiste o token, lease, número de tentativas e orçamento. A rede é consultada sem manter transação de escrita aberta. Antes de persistir resultados, outro UPDATE verifica token e validade do lease e obtém o lock de escrita. Resultado, evidências e conclusão da tarefa são gravados na mesma transação.

Um processo antigo com lease vencido não consegue gravar após outro claim. Reinício pode repetir **leituras externas**, mas não regrava efeitos já concluídos daquele item. Não se promete exactly-once de requisições de rede. Pausa/cancelamento durante uma consulta são revalidados antes de salvar; o resultado em trânsito é descartado. Erros temporários usam até três tentativas com backoff. Falha de configuração não é repetida indefinidamente. Exceções brutas de provedores não vão ao estado público/log do worker.

Há um executor global por banco SQLite, um intervalo mínimo compartilhado entre tarefas e um orçamento diário persistente, em UTC. O orçamento contabiliza tarefas/tentativas, não cada subrequisição HTTP interna nem valor financeiro faturado pelo provedor. Não é um scheduler distribuído de alta capacidade. O lease padrão de 300 segundos limita a validade de uma execução: uma consulta que ultrapasse esse prazo perde autoridade de escrita e será recuperável.

O modo legado é explícito e usa o mesmo mecanismo de claim. O processo contínuo recusa inicialização em modo legado. Não altere o modo com executores antigos ainda ativos: pare os processos, aguarde ou recupere leases em ambiente controlado e reinicie todos com a mesma configuração. Não há dois sistemas de fila concorrentes.

Monitores reutilizam seus filtros de oportunidade e o mecanismo de descoberta existente. O worker atualiza resultados e próxima execução; a API recusa gravações de resultados pelo navegador em monitor controlado pelo servidor. Reativar/agendar explicitamente um monitor permite nova tentativa após erro terminal.

## Interface e referências

A composição coloca identidade e diagnóstico antes da prioridade e da próxima ação, seguida de inspeção progressiva das evidências e preparação de abordagem. Formulários secundários ficam em expansões. A ficha permanece montada durante trocas de aba, preservando edições de mensagem; fechar com alterações pede uma decisão explícita. A proteção também sinaliza saída da página.

Referências consultadas: [Refero](https://refero.design/), [Attio](https://attio.com/) e [Linear](https://linear.app/). A composição mantém tokens carvão/crimson/off-white e os componentes existentes, sem copiar telas. Não foi acessada uma biblioteca privada do Refero Styles.

## Limites de infraestrutura

Testes locais não homologam Railway, HTTPS, PostgreSQL, dispositivos físicos ou operação 24/7. Web e worker precisam do mesmo banco/volume persistente. Com SQLite, use um host e volume compartilhado localmente; não distribua réplicas em volumes independentes. O serviço precisa permanecer ativo para progresso sem navegador. Consulte INSTALL e VALIDATION da v1.31.
