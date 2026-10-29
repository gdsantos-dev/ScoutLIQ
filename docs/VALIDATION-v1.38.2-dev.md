# Validação — ScoutLIQ v1.38.2-dev

Entrega de desenvolvimento validada localmente em Windows, Python/SQLite e Chrome desktop headless. Base exata v1.38.1-dev conferida por SHA256 e manifesto. Instalação pessoal e fontes da base preservadas. Sem deploy, envio comercial, investigação automática ou consumo de cota real de provedor.

## Resultado final

| Verificação | Resultado |
|---|---|
| Regressão backend integral | **407 aprovados**, 222,22 s; nenhum reprovado |
| Backend Absorção/migrações após a última proteção de parsing | **59 aprovados**, 51,89 s; inclui 5 casos acrescentados depois da regressão integral |
| Frontend unitário | **23 aprovados**, 7 arquivos |
| Build produção / TypeScript frontend | Aprovados |
| Tipagem E2E | Aprovada |
| E2E — todas as 13 suítes disponíveis | **65 aprovados**, consolidados após correções e repetições das suítes afetadas |
| Migrações | Instalação limpa 029, upgrade 028→029, preservação por tabela, FK/integridade e recusas de downgrade aprovados |
| Compatibilidade protegida | **36 arquivos idênticos** à base: motores selecionados e todas as 28 migrações históricas |
| Segurança do fluxo novo | Autorização por usuário, CSRF, mass assignment, parsing, idempotência, concorrência, cache próprio, lease, cancelamento e orçamento testados |

A execução integral contém 407 testes. Depois dela, a proteção contra números não finitos acrescentou 5 casos; os 59 casos relacionados foram executados novamente. Portanto, foram verificados 412 casos backend distintos ao longo do ciclo, sem alegar uma única execução integral de 412. Os 59 não devem ser somados aos 407 como se todos fossem novos.

E2E: Busca Geral 3; Busca Unificada 9; mapa 1; busca inteligente 3; Absorção legada 5; Absorção Inteligente 4; automações 2; experiência 3; workflow 5; redesign/regressão visual existente 25; aprendizado 2; inteligência 2; comunicação 1. Não foi iniciado um redesign: essa suíte apenas verificou a interface preservada.

As duas suítes de Absorção foram repetidas após o ajuste visual final, nas portas 8360/8361. As demais passaram com os mesmos módulos funcionais preservados. A suíte semântica passou na porta 8351 depois do ajuste de fixture descrito abaixo. `validation-evidence.json` registra contagens, hashes dos logs e comparações de fontes.

## Casos e limites verificados

- CSV UTF-8/BOM, aspas, quebras de linha, separadores, cabeçalhos desconhecidos/duplicados e mapeamento explícito; JSON e tabela colada; originais e colunas ignoradas preservados.
- Máximos de tamanho/quantidade; formatos inválidos por linha; rejeição de NaN/Infinity/overflow; números finitos com vírgula e notação científica.
- Normalização sem inferir país ou DDI; URLs/credenciais/esquemas inválidos; campos privilegiados recusados.
- Lote parcial, correção posterior, segunda confirmação, replay após perda de resposta, nenhuma recriação de Lead e bloqueio de edição do item já importado.
- Duplicatas dentro/entre lotes e contra Lead canônico; IDs de fonte preservados; filiais distintas; decisão humana persistente; reavaliação após correção em outro lote.
- Provedor controlado: correspondência única, candidatos ambíguos, aceitação/rejeição, cidade/estado divergentes, resultado administrativo recusado, fontes incompatíveis, indisponibilidade e timeout.
- Cache por usuário antes de rede, autorização externa explícita, reservas duráveis, ledger HTTP real com transporte substituído em teste, limite global, retries e prazo.
- Lease expirado/reinício, pausa/retomada/cancelamento, resultado tardio depois de edição, ausência de Lead ou mensagem como efeito de recuperação.
- Desktop/320/390, overflow, teclado/Escape/foco, seleção de arquivo e axe WCAG A/AA; captura e inspeção visual de desktop e mobile. Não equivale a homologação em aparelho físico ou leitor de tela.

## Falhas encontradas e resolvidas durante a execução

1. A reversão inicial de 029 reconstruía a tabela-pai no SQLite e podia ativar cascatas. Corrigida com remoção nativa de colunas e bloqueio de perda de originais/auditoria. Testes repetidos preservaram staging e tabelas históricas.
2. Histórico expandido rolável sem foco pelo teclado. Corrigido com foco/identificação da região de texto; axe passou novamente.
3. A suíte semântica antiga falhava com HTTP 422 antes de iniciar a busca. A mesma falha foi reproduzida na base v1.38.1-dev, porta 8340, no mesmo teste. A fixture enviava `search_mode=ambiguous` embora o schema semântico atual exclua esse metadado. A fixture foi alinhada ao contrato removendo o campo simulado; nenhum motor semântico/produto foi alterado. As duas verificações passaram na porta 8351.
4. Parametrização de um teste com 48 mil caracteres no nome ultrapassou limite de variável de ambiente do Windows. IDs curtos de teste corrigiram o problema; limite real de entrada foi mantido.

Avisos herdados: deprecações TestClient/AnyIO e chunk do mapa acima de 500 KB. Não foram omitidos nem tratados como testes aprovados por dispensa. Não surgiram falhas remanescentes nas suítes locais executadas.

## Estado da entrega

| Estado | Escopo |
|---|---|
| Implementado e testado localmente | Importação, edição, auditoria, recuperação limitada, sugestões, dedup, confirmação incremental, migração e UX descritas |
| Homologado externamente | **Nenhum provedor/ambiente real nesta execução** |
| Parcial por capacidade da fonte | Recuperação externa Geoapify exige cidade/país e limita a 5 candidatos; nomes comuns ou ausência de contexto podem permanecer pendentes; OSM/demo não têm recuperação comercial compatível neste ciclo |
| Dependente de homologação/configuração | Credenciais/cobertura Geoapify reais, PostgreSQL, Docker/Railway, HTTPS público, dispositivos físicos e auditoria externa atualizada de dependências |
| Fora deste ciclo | Investigação progressiva automática pós-entrada, campanhas/contatos e novos ajustes de Score |

A classificação “pronto” significa elegibilidade técnica e identidade suficientemente sustentada para o contrato canônico. Não comprova qualidade comercial, ausência de site, intenção de compra ou conversão.

## Pacotes e evidências

FULL e PATCH são fontes; dependências, dist, `.env`, bancos, logs de runtime e caches não acompanham os ZIPs. A migração 029 e as instruções de instalação estão incluídas. O aplicador não faz deploy nem migra banco.

`release/PACKAGE-VALIDATION.json` é o recibo do empacotamento: hashes da base/FULL/PATCH, equivalência do PATCH ao FULL, dry-run sem alterações, conflito recusado, runtime sintético preservado, reaplicação recusada e restauração de fontes. `release/SHA256SUMS.txt` fornece os checksums finais. A aprovação desse recibo é requisito para a entrega dos ZIPs.

[Dados de validação](qa-v1.38.2-dev/validation-evidence.json) · [Desktop](qa-v1.38.2-dev/absorption-intelligent-desktop.png) · [Mobile 320](qa-v1.38.2-dev/absorption-intelligent-320.png) · [Mobile 390](qa-v1.38.2-dev/absorption-390.png)

[Arquitetura e segurança](ABSORPTION-INTELLIGENT-v1.38.2-dev.md) · [Changelog](CHANGELOG-v1.38.2-dev.md) · [Instalação/rollback](INSTALL-v1.38.2-dev.md) · [Checkpoint](CHECKPOINT-v1.38.2-dev.md)
