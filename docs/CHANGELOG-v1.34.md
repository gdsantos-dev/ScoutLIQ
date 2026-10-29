# ScoutLIQ 1.34.0 — P0.2, inteligência comercial

Base exclusiva: FULL v1.33.0, SHA256 `f4915a73ffc2231e092ae9397c23c7bcd42f44213fb5567ca1d97c4be3d6b03e`. Os 256 arquivos do manifesto foram conferidos antes da extração em pasta nova. Data da entrega: 17/10/2026.

## Implementado

- Interpretação semântica opcional via OpenAI Responses API, com modelo explícito, schema estrito e validação local. Texto do pedido é dado; não há ferramentas, navegação, contatos, execução de comandos ou alteração do Score pelo modelo. O resultado continua sendo o Intent editável existente. Qualquer recusa, limite, falha ou resposta inválida usa o interpretador determinístico.
- Reserva persistente e serializada de tokens por instalação/usuário/dia UTC; idempotência por solicitação. Nenhum reembolso automático de chamada falha ou incerta. A exclusão da conta preserva o consumo global sem vínculo com o usuário. Migração aditiva 023.
- Planejamento finito por setor: uma primeira página por setor suportado; depois rendimento técnico observado por página com exploração de setores menos visitados. Cada cursor fica no SmartSearch existente. Setores sem cobertura são explicitados e não impedem a coleta dos setores suportados. Dois resultados repetidos encerram aquele setor. Nenhuma fonte genérica ou demo é selecionada implicitamente.
- Investigação contextual do HTML já coletado: links de serviços/cardápio, contato/formulário e sinal de agendamento. Evidências ficam na OpportunityEvidence, por URL, como prováveis e sujeitas à revisão/TTL. Não se afirma ausência comercial com HTML truncado.
- Contatos públicos explícitos da página inicial e das páginas da auditoria existente, incluindo e-mail com procedência. Domínios de WhatsApp/Instagram são verificados por host, não por substring. Números diferentes não são escolhidos automaticamente; valores do operador não são sobrescritos. E-mail observado não é convertido em pessoa/decisor ou autorização de envio.
- Resultado de pesquisa não confirmado não preenche a cascata de enriquecimento.
- Mesma prioridade Score 3.0, mesmos pesos e mesmas rotinas/limites/ledger de P0.1. As rotinas não chamam o modelo: executam a intenção já revisada e salva.
- UX restrita ao seletor opcional na Busca inteligente, plano consultável no resultado e contatos com fonte na ficha existente.
- Avaliação reproduzível de seleção e ordenação em sete casos sintéticos herdados; métricas distinguem rótulos controlados, revisão humana e resultados comerciais.

## Limites da entrega

Esta é uma fatia funcional P0.2, não a conclusão integral do Prompt 2/3. Não há evidência de melhora de conversão ou seleção em empresas reais. P0.3 e P0.4 continuam pendentes, delimitadas em [CHECKPOINT-v1.34.md](CHECKPOINT-v1.34.md). Nenhum redesign do Prompt 3 foi iniciado. Não houve envio comercial nem deploy.
