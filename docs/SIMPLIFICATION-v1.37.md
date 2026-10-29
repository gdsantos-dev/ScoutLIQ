# Simplificação dos fluxos — v1.37

| Tarefa | Antes | Agora |
|---|---|---|
| Iniciar busca simples | Entradas territorial/inteligente; interpretação/revisão separadas | Uma ação Buscar empresas; 3 campos; lançamento direto |
| Escolher mecanismo | Determinístico ou semântico exposto no processo | Política de instalação; determinístico primeiro, semântica opcional com orçamento |
| Selecionar local | Texto geográfico misturado à descrição | Catálogo separado, ID selecionado explicitamente |
| Ajustar filtros | Formulário amplo de preparação | Ajustar critérios recolhido; apenas dúvidas materiais interrompem |
| Acompanhar | Modal misturava formulário, histórico, resultados e revisão | Progresso e histórico no Radar; detalhes técnicos recolhidos |
| Revisar empresa | Controles dentro da busca | Ficha contextual, na aba Análise |
| Confirmar avaliação existente | Redigitar uma justificativa | Botão explícito reutiliza justificativa ou registra a avaliação exibida |
| Alterar classificação | Justificativa manual | Continua exigindo evidência/motivo, versão e autoria |
| Reutilizar consulta antiga | Caminho separado de descoberta | Mesmo job e worker, sem descartar predicados históricos |
| Pesquisar mapa | Outra ação de coleta | Área como restrição do mesmo formulário |

A confirmação rápida não modifica fatos desconhecidos, não remove bloqueios, não autoriza contato nem gera confirmação humana automática. O backend recusa mudanças de campos no modo confirm_existing; exceções sensíveis precisam de justificativa própria.

Medições verificáveis: 3 controles iniciais no diálogo, meta padrão 50 e opções 25/50/75/100; zero seletores obrigatórios de provedor/modelo; zero chamadas a /radar/search nos E2E novos de mapa e reexecução legada. Não foi realizado estudo de tempo com operadores reais; não há percentual inventado de ganho de produtividade.
