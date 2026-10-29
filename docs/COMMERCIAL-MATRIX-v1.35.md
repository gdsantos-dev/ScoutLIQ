# Matriz de avaliação comercial

Separar sempre adequação da oportunidade, concordância com avaliação humana e resultado posterior. Resposta não prova oportunidade de qualidade; ausência de resposta não prova falso positivo.

| Caso controlado | Resultado esperado | Onde verificar |
|---|---|---|
| Humano adequado / sistema selecionou | TP | reviewed_metrics, comparação por caso |
| Humano inadequado / sistema selecionou | FP | Comparação/hipótese de calibração |
| Humano adequado / sistema rejeitou | FN | Recall e comparação por caso |
| Humano inadequado / sistema rejeitou | TN | Matriz de confusão |
| Humano incerto ou não revisado | Não entra na matriz binária | Cobertura e casos excluídos |
| Sistema absteve | Não vira FN silenciosamente | Abstenção, positivos abstidos e cobertura de decisão |
| Score externo declarado | Identificado como externo | Coorte e versão; sem dimensões nativas não calibra |
| Classificação humana corrigida | Nova revisão; história intacta | LearningRevision e import receipt |
| Mesma empresa em ambos os splits | Comparação recusada | Proposta exige desenvolvimento/validação sem sobreposição |
| Sugestão reduz FP mas aumenta FN | Regressão explícita | before/after e casos alterados nos dois conjuntos |
| Amostra pequena | Valores descritivos e limitação visível | Mínimos pragmáticos, intervalo Wilson, sem alegar ganho |
| Resultado reunião/proposta/ganho/perda | Dimensão posterior separada | Outcome com data/referência; não altera rótulo automaticamente |
| Reply de interesse | Contexto e próxima ação | LeadActivity; não transforma classificação em TP |
| Opt-out | Suprimir/cancelar contatos | RecipientPolicy e outbox, sem reclassificar oportunidade |

Os sete fixtures herdados e os cenários adicionais são sintéticos. A comparação de 175 entradas contra o código do ZIP v1.34 comprova equivalência do Score padrão nesses casos, não precisão comercial real. Zero casos ORLIQ reais foram fornecidos nesta execução. Não há medição representativa de conversão, ganho de seleção, economia de tempo ou efeito causal de uma calibração.

Para medir melhoria, importar casos revisados com identidade, fonte/evidência e decisão humana explícitas; separar desenvolvimento/validação antes da hipótese; conservar versões dos critérios e registrar resultados posteriores. Comparar métricas, tamanho/cobertura e regressões por setor/região. Repetir com um novo conjunto de validação quando os mesmos exemplos já tiverem influenciado a escolha dos parâmetros.
