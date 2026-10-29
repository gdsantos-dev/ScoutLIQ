# Aprendizado comercial supervisionado — P0.3

Implementação da v1.35 em desenvolvimento, extraída exclusivamente do FULL v1.34.0. Esta fatia não implementa comunicação externa. A versão pública permanece 1.34.0 enquanto a missão v1.35 não está consolidada.

## Uso

Na ficha de uma oportunidade, abra **Operação → Revisão comercial supervisionada**. Informe conjunto, divisão da amostra, revisor, data, avaliação, justificativa e evidência. Serviços adequados, prioridade e resultado comercial ficam separados. Confira a prévia e ateste a revisão humana antes de confirmar. Casos de demonstração não entram como amostra humana.

Em **Gerir clientes → Histórico**, a seção **Casos revisados e qualidade da seleção** permite importar JSON, corrigir casos, consultar histórico, registrar avaliações e examinar calibrações. A navegação anterior foi preservada; não há dashboard paralelo. A revisão não altera automaticamente a qualificação operacional do Lead, suas evidências ou o Score.

A origem humana é uma declaração do operador autenticado, registrada com sua identidade e confirmação. O sistema não consegue provar quem escreveu um arquivo externo; não transforma uma classificação de IA em humana. Não lê chats do ChatGPT.

## Contrato de importação

Arquivo UTF-8 contendo uma lista de objetos; até 50 registros, respeitando o limite HTTP total de 65.536 bytes (o seletor de arquivos orienta 64 KB). Até 2.000 empresas por conta, 50 prévias pendentes, 100 confirmações por dia UTC. Prévia expira após 24 horas. Nenhuma URL fornecida é acessada. O servidor valida novamente tudo; o nome do arquivo não é usado como caminho.

Exemplo de estrutura externa, apenas ilustrativo — não é um caso comercial real:

```json
[
  {
    "source": "orliq_manual",
    "external_id": "caderno-001",
    "expected_version": 0,
    "company": {
      "name": "Empresa de exemplo",
      "country": "BR",
      "city": "Recife",
      "region": "PE",
      "sector": "Cafeteria",
      "address": "Endereço de exemplo, 1"
    },
    "dataset": "ORLIQ revisão",
    "split": "validation",
    "reviewed_on": "2026-10-18",
    "reviewer": "Nome do revisor",
    "label_origin": "human",
    "classification": "uncertain",
    "justification": "Registrar aqui o motivo e os limites da avaliação manual.",
    "services": [],
    "operator_priority": "unknown",
    "review_status": "needs_review",
    "evidence": [{"statement": "Observação revisada pelo operador.", "reference": "Referência verificável ao registro manual."}],
    "outcome": "unknown"
  }
]
```

Para Lead existente, substitua `company` por `lead_id`. Não envie `company` nem `system_observation`: o servidor obtém identidade e Score, com versão do Lead. A evidência pode referenciar um `evidence_id` pertencente à mesma oportunidade e conta. O snapshot guarda também a observação e sua referência; não muda a classificação de OpportunityEvidence.

Caso externo exige nome, país, cidade, setor e endereço ou telefone internacional. Homônimos não são fundidos apenas por nome/cidade. Uma empresa já identificada no CRM deve ser vinculada ao Lead existente. Não há outro cadastro de empresas ou inserção automática de Lead.

`classification`: `suitable`, `unsuitable`, `uncertain`. `split`: `development` ou `validation`. `source`: `orliq_manual` ou `external_review`. `review_status`: `reviewed` ou `needs_review`. Campos extras, datas futuras, serviços fora do catálogo e rótulo `ai` são recusados. Para resultados além de `unknown`/`not_contacted`, informe `outcome_on` e `outcome_reference`. Sem resposta não implica inadequação; resposta não implica oportunidade adequada.

Um Score externo opcional usa `system_observation` com `score` de 0 a 100, `decision` (`selected`, `rejected`, `abstained`), `criteria_version`, `evaluated_on` e `reason`. É marcado **external_declared**, nunca recalculado nem verificado como dado nativo. Sem observação externa, a decisão é abstenção e o score é desconhecido.

## Transação, idempotência e revisão

1. `POST /api/learning/imports/preview`: `{request_key: UUID, records: [...]}`. Erros por registro, comparação anterior/nova e hash da prévia. Nenhum caso é criado.
2. `POST /api/learning/imports/{id}/commit`: `{preview_hash, confirm_human_reviews: true}`. Só o dono pode confirmar; CSRF obrigatório. Um erro ou conflito reverte o lote inteiro.
3. Repetir a mesma chave com outro conteúdo gera 409. Repetir a confirmação retorna o recibo original, mesmo após correção posterior. Reimportação idêntica gera `unchanged`, sem nova revisão.
4. Correção usa o mesmo `source`/`external_id` e `expected_version` atual. Cada alteração gera revisão imutável e, se vinculada, LeadActivity. A identidade de um caso não pode ser trocada.

Gate transacional, unicidades e versões otimistas protegem corridas. O commit verifica novamente versão do caso, estado/Score do Lead, propriedade de evidências e duplicação. Uma prévia não é autorização para sobrescrever trabalho feito depois dela. Fechar navegador ou perder a resposta não exige criar outra chave: consulte a prévia/recibo ou repita a mesma confirmação.

Leads removidos não apagam os snapshots de revisão. O vínculo é SET NULL; o registro histórico conserva a referência original. A edição de um caso originalmente vinculado exige a oportunidade disponível; não há religação automática nem troca silenciosa de identidade. Exportação preserva esses registros.

## Métricas e conjuntos versionados

`POST /api/learning/evaluations` recebe `request_key`, `dataset`, `split` e `k` (1–100). Congela casos, versões, rótulos, motivos, evidências, scores e resultados conhecidos, com hash do conjunto. Correções futuras não alteram avaliações antigas. Limite persistente: 30 avaliações/dia UTC.

`backend/selection_quality.py` continua sendo a função de métricas. A avaliação registra:

- TP/FP/FN/TN, precisão e recall somente de rótulos humanos conclusivos e decisões binárias;
- cobertura humana, cobertura de decisão, taxa de abstenção e positivos humanos abstidos;
- precisão@K e NDCG nos casos rotulados com score observado, incluindo abstenções; `effective_k` explicita o tamanho disponível;
- comparação por caso, setor, região e origem/versão do critério;
- resultados comerciais em contagem separada; sem converter respostas em rótulos;
- intervalo Wilson descritivo da precisão e limitações da amostra.

O indicador de amostra exige 30 decisões, 10 seleções e 10 positivos humanos. É uma regra operacional de prudência, não uma certificação estatística de suficiência. Amostras menores continuam mostrando contagens descritivas e aviso. Mesmo acima do limiar, seleção manual, dependência entre exemplos e representatividade precisam de avaliação. Scores externos/versões diferentes não são necessariamente comparáveis.

A decisão nativa corresponde ao estado do Score 3.0, não aos filtros adicionais de uma intenção de busca. `qualified` vira seleção; `evaluated`/`incompatible`, rejeição; estados provisórios/insuficientes, abstenção. Não confundir rejeição com ausência de investigação.

O avaliador existente aceita uma exportação explícita da conta:

```powershell
python scripts/evaluate_commercial_quality.py --reviewed-export export.json --dataset "ORLIQ revisão" --split validation --output artifacts/reviewed-quality.json
```

Sem argumentos, continua executando os sete fixtures sintéticos herdados. Esses fixtures e os registros de QA **não comprovam melhoria comercial real**.

## Critérios, hipóteses, aprovação e reversão

O cálculo canônico de Score 3.0 usa `score_criteria.commercial_priority` tanto na operação quanto na reprodução de dimensões congeladas. Não existe um segundo score concorrente. Configuração padrão mantém exatamente pesos 25/25/20/20/10, cobertura 80, limiar 60 e necessidade 65. Os portões de compatibilidade, atividade, necessidade, contradição e contato continuam obrigatórios.

Uma proposta exige avaliações separadas de desenvolvimento e validação, sem empresas repetidas. A hipótese automática testa apenas limiares 70/80/90 e escolhe usando desenvolvimento; não aplica nada, nem usa validação para escolher. Se nenhuma hipótese melhora concordância, retorna uma explicação. O operador também pode propor pesos (5–50 cada, soma 100), cobertura (80–100), seleção (60–95) e necessidade (65–95). Modelos de linguagem não participam desse processo.

A comparação usa os mesmos snapshots antes/depois e registra hipóteses, casos de suporte, evidências, amostras excluídas, mudanças, regressões e limitações separadas por divisão. Scores externos sem dimensões nativas não sustentam calibração. A amostra precisa ter ao menos um rótulo conclusivo nativo em cada divisão; amostras pequenas exigem ciência explícita dos limites. A interface nunca apresenta essa aprovação como prova de ganho comercial.

Aplicar exige hash da comparação, versão vigente, `approve_score_change` e `acknowledge_sample_limits`. Revisões alteradas ou configuração desatualizada recusam a aplicação. Pesquisas ativas na conta devem terminar ou ser canceladas. Até 5.000 Leads são atualizados em uma transação; contas acima desse limite são recusadas, pois aplicação incremental ainda não existe.

Cada aplicação registra configuração anterior/nova, ator pela conta autenticada, motivo e histórico por Lead com scores antes/depois. Novos Leads herdam apenas a configuração aprovada da própria conta. A alteração da versão do Lead invalida aprovações de outreach vinculadas ao estado antigo, conforme o mecanismo já existente. Avaliações, resultados e decisões históricas permanecem congelados.

Somente a alteração vigente pode ser revertida, com nova aprovação e motivo. Reversão cria outro evento/versão, não apaga a aprovação anterior. Voltar ao padrão restaura o motor `3.0`. Reaplicar uma requisição já concluída retorna seu recibo; não executa a alteração novamente. Limite de 30 propostas/dia UTC e limites de frequência nas operações.

## Migrações e preservação

024 adiciona casos, revisões, prévias e avaliações. 025 adiciona configurações, propostas, histórico e `leads.score_criteria_json` com padrão `{}`. Sem calibração aprovada, todos os scores seguem o comportamento da v1.34.

Downgrade 025 recusa configurações não padrão. Reverta explicitamente para o padrão e exporte histórico antes de descer versões. O downgrade usa DROP COLUMN nativo para não recriar Leads e disparar CASCADE; SQLite precisa suportar essa operação (3.35+). Os testes verificam todos os campos canônicos da v1.34, evidências, rascunhos, integridade e chaves estrangeiras. Downgrade remove as tabelas novas: restauração completa exige backup consistente.

`/api/export` inclui `commercial_learning`: casos, revisões, avaliações congeladas, recibos confirmados, critérios, propostas e histórico. Não exporta prévias não confirmadas. Nenhum dado pessoal foi migrado durante o desenvolvimento; somente bancos sintéticos.
