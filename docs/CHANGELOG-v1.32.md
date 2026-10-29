# ScoutLIQ 1.32.0 — mudanças e estado

Base: FULL 1.31.0, SHA-256 `3f3420d3429c309220171eadaa5dcbafcd1134941ea54b073c1fa9bccd798c1f`. Trabalho isolado; instalação pessoal e versões anteriores preservadas.

## Implementado

- Entrada Busca inteligente no Radar existente; descrição, meta, resumo editável, execução e histórico.
- Intenção comercial estruturada, requisitos/preferências e ambiguidades explícitas.
- Adequação central por origem, motivos de descarte e revisão auditável de autonomia, porte, operação e B2B.
- Prioridade 3.0 no motor existente, estados desconhecidos/contraditórios, cobertura e snapshot 2.5 na migração.
- Descoberta progressiva, deduplicação de identidade/filiais, paginação limitada e controle de cobertura.
- Orquestração persistente no executor existente, compartilhando lote, pesquisa, evidência e orçamento.
- Pausar, retomar, cancelar, recuperar lease e concluir parcialmente sem inflar a meta.
- Pesquisas salvas com intenção completa; monitores legados preservados.
- Dados sintéticos comparativos, documentação operacional e migração 021.

## Testado

Ver `VALIDATION-v1.32.md` para comandos, contagens e limites da evidência local. Os casos de classificação, progressão e quantidades usam fontes controladas. Não são ensaios comerciais reais.

## Parcial

- Linguagem natural é determinística e limitada ao vocabulário declarado; negações livres, números e expressões ambíguas exigem correção no resumo.
- Cobertura internacional depende de cidade/setor e da fonte; nenhum adaptador fornece busca nacional completa. OSM não pagina de forma confiável e Geoapify não tem mapeamento específico neste adaptador para todos os nichos B2B.
- Atividade social, independência e porte não disponíveis na fonte permanecem desconhecidos. Revisão manual está pronta; inferência autônoma desses fatos não foi fabricada.
- Calibração usa fixtures sintéticas. Avaliação humana de empresas reais e resultados comerciais ainda não estão disponíveis no conjunto.

## Bloqueado externamente

Homologação de produção e ensaios de qualidade com empresas reais dependem de ambiente/provedores configurados e amostra comercial revisada. A implementação local não requer uma API paga nova; a ausência desses ensaios não é apresentada como sucesso real.

## Não iniciado por escopo

Envio Gmail/WhatsApp, agente proativo, recorrência autônoma de intenção comercial, treinamento automático de pesos e redesign integral.

## Pendências objetivas para o Prompt 2

1. Escolher uma amostra real por nicho/mercado com revisão humana de adequação, evidência, autonomia e contato; preencher `human_label`, `human_reason` e resultado real, sem exportar dados privados desnecessários.
2. Medir precisão das qualificadas, taxas de descarte, cobertura, duplicação, custo por candidata e tempo até qualificação; comparar com a prospecção manual sem alegar conversão antes de observar resultados.
3. Decidir fontes adicionais somente onde o catálogo atual não cobre o nicho. Implementar o contrato explícito de páginas/capacidades e testar custo, território e falhas.
4. Evoluir interpretação de números, negações e expressões compostas com testes; eventual LLM deve produzir o mesmo DTO e manter revisão/limites.
5. Avaliar inteligência e autonomia recorrente somente após esse conjunto supervisionado. Não ligar recorrência nem mensagens automaticamente como consequência de aprovar esta versão.
6. Homologar supervisor, volume compartilhado, produção/HTTPS e, se utilizado, PostgreSQL. Preservar a distinção entre aprovação de conteúdo e autorização de envio.
