# Prioridade comercial 3.0

## Auditoria anterior

O motor 2.5 distribuía 50 pontos por necessidade digital, 20 por demanda pública, 20 por contato e 10 por atividade. Campos desconhecidos começavam em zero. Geoapify/OSM normalmente não forneciam avaliações: isso removia até 20 pontos independentemente do potencial real. Site ausente na fonte rendia 10 pontos; ausência declarada de site, sozinha, rendia 50. A exclusão de redes existia apenas no normalizador Geoapify.

O conjunto sintético foi executado antes da edição e congelado para comparação. Não são avaliações de empresas reais nem juízos de um vendedor humano.

## Fórmula única

`backend/scoring.py:score` continua sendo a prioridade principal usada por Radar, ficha, campanhas, automações e listas. Fórmula comercial 3.0:

| Dimensão | Peso | Fundamento |
|---|---:|---|
| Adequação ao perfil | 25 | Categoria comercial, exclusões e autonomia revisada |
| Necessidade | 25 | Ausência registrada ou problemas nas páginas realmente consultadas |
| Impacto potencial | 20 | Relação entre necessidade e nicho; estimativa, não receita prometida |
| Viabilidade | 20 | Canal de contato público, sujeito a bloqueio e autorização de envio |
| Atividade | 10 | Atividade registrada ou site acessível; escopos distintos |

Cada dimensão tem valor 0–100 ou `null`, estado (`verified`, `unfavorable`, `uninvestigated`, `contradictory`) e justificativa. Cobertura é a soma dos pesos observados. Média ponderada usa apenas dimensões observadas, mas passa por travas: necessidade, contato, atividade e adequação suficientes; cobertura mínima de 80%; necessidade mínima de 65 e prioridade mínima de 60 para `qualified`. Sem isso, prioridade provisória fica limitada a 49 e é identificada como provisória/insuficiente. Incompatibilidade ou opt-out resulta em 0 e estado incompatível, distinto de informação insuficiente.

Um site e uma ausência simultaneamente registrados produzem contradição. Análises com mais de 90 dias precisam ser renovadas. Ausência de avaliações não é desfavorável; avaliações sozinhas não elevam prioridade. Instagram informado não significa ativo. Acessibilidade do site é um sinal limitado, não comprovação completa de operação atual. Autonomia e B2B requerem fatos próprios, não são derivados do número de avaliações.

Os diagnósticos técnicos, confiança e adequação de serviços anteriores continuam como informações auxiliares. Não somam um segundo score principal. `dimensions` e `reasons` preservam esse contrato técnico; `commercial_dimensions` explica a prioridade 3.0. Campos não observados deixam de gerar lacunas de nicho automaticamente.

Avaliações públicas só aumentam o impacto quando já existe necessidade verificada: pelo menos 100 avaliações e nota 4,5 adicionam até 20 pontos à dimensão impacto, limitada a 100. Em avaliação completa, isso representa no máximo quatro pontos da prioridade principal. Quantidade ausente permanece desconhecida.

## Antes/depois controlado

| Caso sintético | 2.5 | 3.0 | Estado novo |
|---|---:|---:|---|
| Cadastro esparso | 10 | 49 | Insuficiente; não comparável a avaliação completa |
| Empresa com necessidade, contato e atividade verificados | 78 | 85 | Qualificada |
| Rede conhecida com muitas avaliações | 76 | 0 | Incompatível |
| Prefeitura | 56 | 0 | Incompatível |
| Apenas muitas avaliações | 30 | 49 | Insuficiente |
| Apenas ausência de site | 50 | 49 | Provisória |
| Site saudável auditado | 21 | 46 | Avaliada, sem necessidade suficiente |

49 nos casos incompletos é teto de uma estimativa parcial, não evidência de oportunidade média; a interface mostra a qualificação provisória. A ordenação usa o estado/adequação refletidos nas travas e desempata por preferências verificadas. Os pesos são uma regra explícita de produto, sem alegação de calibração estatística ou conversão validada.

## Rastreabilidade e avaliação

A migração 021 congela em `previous_score_json` o valor e as dimensões 2.5 de cada lead existente. Novos leads não recebem um histórico fictício. Revisões de autonomia, atividade, B2B e porte registram antes/depois e motivo em `LeadActivity`.

`tests/fixtures/commercial-evaluation-v132.json` contém entradas, valor anterior, atual, rótulo de controle, motivo, `human_label`, `human_reason` e `outcome`. Os três últimos permanecem nulos enquanto não houver avaliação humana/resultado real. Não foram lidos outros chats nem inventados resultados comerciais. O conjunto serve para comparação controlada; não altera pesos automaticamente. A ficha mantém os resultados comerciais já existentes para futura avaliação supervisionada.
