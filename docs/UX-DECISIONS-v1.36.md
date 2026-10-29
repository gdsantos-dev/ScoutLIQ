# Auditoria e decisões — v1.36

## Constatações na base

- `WorkspaceShell.tsx`: duas barras horizontais, quatro destinos de operação, seis de gestão; automações e integrações só aparecem no menu da marca. A troca lembra a última página, mas telas desmontadas podem perder estado local.
- `Radar.tsx`: 2.500+ linhas; mapa como visualização inicial, pesquisa simples e inteligente competem. Linhas omitem próxima ação e estado de qualificação.
- `ContextPanel.tsx`: cinco abas e resumo distinto por ambiente; `OpportunityWorkflow` acumula diagnóstico, evidências, editor, envio, política e aprendizado em sequência. Preservar guardas de rascunho sujo.
- `SmartSearch.tsx`: descrição/meta já existem; formulário de interpretação mostra setores e requisitos cedo demais. Progresso é real, mas contém jargão de execução.
- `OperationalRoutines`: configurações e histórico existentes; manter limites e status sem chamar infraestrutura de ação comercial.
- CSS global acumula blocos de versões anteriores, inclusive múltiplas definições dos mesmos seletores de shell e regras mobile. Não remover por estimativa: extrair regras pelo parser e auditar a remoção.
- As adições de inteligência contêm copy PT não traduzida. Novos textos terão PT/EN/ES; paridade de módulos legados requer conferência explícita.

## Decisões

1. Preservar finalidade Operar / Gerir clientes, com navegação lateral agrupada. Automação torna-se descoberta no shell, configurações ficam no menu da conta. Nenhum destino funcional removido.
2. Radar inicia em lista; mapa acessível por controle rotulado. Pesquisa inteligente é ação principal; pesquisa por local segue disponível. Conteúdo comercial vem dos mesmos Leads/Score, sem recalcular prioridade.
3. Ficha mantém tabs e timeline; ação para abrir trabalho no resumo. Dentro de Operação, evidências, abordagem e revisão humana são etapas navegáveis com DOM preservado, evitando perder edição ao alternar.
4. Busca: descrição + meta; interpretação revisável, critérios detalhados em disclosure. Bloqueios e campos obrigatórios nunca escondidos por conveniência.
5. Shell e novos componentes usam CSS encapsulado; regras substituídas serão removidas dos globais com registro. Não introduzir framework CSS ou pacote.
6. Motion de contexto curto, foco visível, reduced motion, controles de toque e safe area. O mapa não recebe animação decorativa.

## Contratos imutáveis

Backend, migrations até 026, DTOs, Score, regras de contato, OAuth, idempotência e autorização são preservados. Testes usam bancos isolados e adaptadores controlados; nenhum envio comercial real.
