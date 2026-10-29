# Idiomas — v1.37

| Superfície | pt-BR | en-US | es |
|---|---|---|---|
| Entrada de busca, três campos, ajustes | Implementado/testado | Implementado/testado | Implementado/testado |
| Progresso, histórico, grupos e limites | Catálogo existente + novo | Catálogo existente + novo | Catálogo existente + novo |
| Revisão comercial e confirmação | Implementado | Implementado | Implementado |
| Falha de catálogo e erros novos de busca | Implementado/testado | Implementado/testado | Implementado/testado |
| Integrações, navegação, preferências e gestão | Catálogos revisados | Lacunas estáticas corrigidas | Lacunas estáticas corrigidas |

api.ts traduz erros reconhecidos no ponto comum; mensagens do job são traduzidas na apresentação. search.i18n.ts reúne textos funcionais da busca e lacunas herdadas. A auditoria AST procura literais passados a tr e registra ocorrências sem tradução reconhecível em evidence-v137/i18n-static-audit.json. É uma verificação estática, não certificação linguística de cada mensagem dinâmica.

Nomes, localidades, justificativas humanas, evidências, conteúdo coletado e diagnósticos não catalogados mantêm o idioma original. Não se traduz informação comercial automaticamente com um modelo pago. Políticas, qualidade da fonte e cobertura internacional não são inferidas do idioma da interface.

E2E de preferências verifica persistência en-US/es, moeda/identidade; experience.spec.ts verifica o formulário de 3 campos e erro de catálogo nos dois idiomas. O fluxo completo principal é exercitado em pt-BR. A revisão humana de toda a terminologia por falantes nativos e leitores de tela reais não foi realizada.
