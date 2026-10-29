# Busca inteligente 2.0 — ScoutLIQ 1.32

No Radar, abra **Busca inteligente**, descreva o negócio e escolha 25, 50, 75 ou 100 oportunidades (50 por padrão). Revise a interpretação e execute. A meta conta somente empresas qualificadas; não conta cadastros brutos, duplicatas ou informações insuficientes.

## Contrato e interpretação

`search_intent.py` valida texto, país ISO, cidade/região, até quatro setores, perfil comercial, requisitos, preferências, exclusões, combinação todos/qualquer, meta e pontos não resolvidos. O interpretador determinístico cobre o vocabulário explícito do catálogo local; não depende de LLM nem promete compreensão livre. País/cidade ausentes, negações livres, limites numéricos e combinações ambíguas pedem revisão. Não inferimos um país inteiro a partir de uma cidade ou reduzimos silenciosamente tecnologia a comércio genérico.

O resumo é editável. “Revisei e corrigi o resumo” reconhece as limitações da interpretação, não aplica termos não suportados. Requisitos restringem a entrega; preferências desempatatam prioridades equivalentes. Porte e autonomia não são inferidos de avaliações. B2B exige revisão comercial do modelo de atendimento. Categorias excluídas ficam preservadas na intenção; pesquisas salvas retêm o contrato completo.

## Pipeline persistente

1. A API cria `SmartSearch` com chave idempotente por conta. Esta tabela guarda apenas intenção, orçamento, cursores e referências aos leads.
2. O mesmo `ResearchExecutor` da v1.31 concede um lease. A coleta ocorre fora de transação; o token é conferido antes de gravar resultado/cursor.
3. `DiscoveryResult` usa o normalizador existente. A identidade comercial continua em `Lead`, com nome/cidade/país e sinais fortes de endereço, telefone e coordenadas. Coordenadas contraditórias impedem juntar filiais que compartilham telefone.
4. `commercial_fit.assess` aplica as mesmas regras independentemente da origem. Redes catalogadas, entidades públicas, encerramento e grande porte registrados são descartados antes de investigação. Revisão de autonomia permite uma exceção de franquia, com motivo no `LeadActivity`.
5. Candidatas insuficientes entram em `ResearchBatch`/`ResearchBatchItem`, modo deep. `WebsiteResearcher` pesquisa a identidade e, quando confirma site, audita páginas. O resultado alimenta `LeadResearch`, o perfil técnico do Lead e a reconciliação de `OpportunityEvidence` da v1.31.
6. Ao terminar a tranche, a prioridade é reavaliada. Se necessário, são investigadas outras candidatas ou coletada outra página/setor. A execução termina ao atingir a meta, esgotar fonte/orçamento, atingir prazo ou ser cancelada.

Não há segundo CRM, pesquisador ou worker. Etapas de pipeline, notas, bloqueios e dados existentes não são apagados. Um lead existente só entra se foi redescoberto na execução; não preenchermos uma meta buscando registros antigos arbitrariamente. Duplicatas têm contador e motivo no grupo de descarte, sem duplicar investigação.

## Estados e controles

`pending`, `running`, `investigating`, `paused`, `cancelled`, `completed`, `partial`. Fechar/recarregar o browser não executa nem interrompe trabalho. O histórico vem do banco. Pausa/cancelamento invalida a gravação de respostas em trânsito; uma requisição externa já iniciada pode terminar. Retomar preserva cursor e identidade. Os controles do lote legado sincronizam o estado da busca associada.

Limites fixos por execução: 12 tentativas de páginas, 600 candidatos brutos, 200 investigações, tranches de até 50, prazo absoluto de duas horas e até três buscas abertas por conta. Pausa não estende o prazo. O orçamento diário UTC do executor é compartilhado (100 tarefas por padrão), e tentativas também o consomem. Isso pode impedir completar 100 oportunidades num dia. O prazo é encerrado mesmo quando o orçamento diário está esgotado, desde que o worker esteja rodando.

Esses limites não são uma previsão financeira: geocodificação, retries HTTP do adaptador e páginas internas da pesquisa podem gerar mais de uma chamada por tarefa. Nenhuma integração paga nova é habilitada. Configure orçamento do provedor e as variáveis existentes antes de operação real.

## Cobertura real dos adaptadores

| Fonte | Implementado | Limite explícito |
|---|---|---|
| Geoapify | Categoria específica, região quando resolvida, páginas de até 100 por offset, sem enriquecimento antecipado caro | Sem categoria específica no adaptador, retorna parcial sem consultar categorias genéricas. Região não resolvida cai no raio já declarado de 5 km. |
| OpenStreetMap/Overpass | Seletores específicos, inclusive `office=it` para tecnologia, coleta de até 100 por setor | Raio de 5 km; sem paginação confiável neste adaptador. Resultado truncado não é declarado cobertura completa. |
| Fonte não configurada/demo | Limitação visível, zero coleta | Não simula descoberta de produção. |

País internacional é aceito com cidade e setor suportados. Tecnologia nos EUA com Geoapify resulta em limitação específica; com OSM consulta a tag de TI na cidade, sem prometer cobertura de todas as empresas B2B. Avaliações e atividade social não são inventadas quando a fonte não as fornece. Não encontrar site, inclusive com erro de acesso, mantém estado desconhecido.

Referências primárias: [Geoapify Places — categorias, limit e offset](https://apidocs.geoapify.com/docs/places/) e [OSM office=it](https://wiki.openstreetmap.org/wiki/Tag:office%3Dit). Capacidade do adaptador não equivale a homologação real de cobertura, disponibilidade ou qualidade.

Extensões implementam `capabilities(sector)` e `search_page(query, offset, limit)` e retornam o contrato normalizado `DiscoveryBatch`. Devem preservar limites, erros seguros, território, proveniência e a camada compartilhada de adequação. O servidor seleciona a fonte configurada; o usuário não injeta URL de provedor.

## Integrações preservadas

As empresas abrem a ficha existente. Evidências, rascunhos, políticas de contato e opt-out seguem a v1.31. Salvar uma intenção usa `RadarSavedSearch`, sem recorrência. Executar pesquisa salva reabre seu resumo completo. Monitoramentos legados permanecem funcionais; ligar um monitor recorrente sobre intenção comercial é recusado explicitamente nesta versão.
