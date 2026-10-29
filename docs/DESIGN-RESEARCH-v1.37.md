# Pesquisa e decisões — v1.37

Consulta em 19–20/10/2026. Este documento separa comportamento descrito nas
fontes, decisão própria e validação local. Não houve sessão autenticada nos
produtos externos nem medição de suas animações. Refero fornece interpretações
normalizadas de estilos; suas páginas de marketing não comprovam o comportamento
de um dashboard em produção. As oito análises abaixo fundamentam decisões de produto; os resultados de
implementação e testes constam no relatório final.

## 1. Pesquisa: Linear Search

Fonte: https://linear.app/docs/search

Problema: entradas concorrentes e interrupção do fluxo para configurar busca.
O manual descreve acesso por `/`, pesquisas recentes e refinamento por filtros.
A contribuição é separar entrada rápida de refinamento, mantendo recuperação
das buscas anteriores. Adaptação: um CTA no Radar, três campos iniciais,
progresso fora do modal e histórico que recupera o job persistido. Descartado:
transportar filtros de issues e navegação de projetos para empresas.
Impacto esperado: menor esforço para iniciar e retomar uma busca, sem inferir
ganho de conversão. Validação: E2E de entrada, recarga e seleção do histórico;
as entradas legadas foram integradas por adaptadores com testes de compatibilidade.

## 2. Pesquisa: Raycast Search Bar

Fonte: https://manual.raycast.com/search-bar

Problema: operador precisa descobrir qual mecanismo usar antes de digitar.
O manual apresenta foco inicial na busca e uma entrada que encontra comandos
e recursos, com configurações de comportamento fora da tarefa imediata.
Adaptação: foco no pedido ao abrir, seta/Enter no catálogo geográfico e ausência
de seletores de modelo/provedor no formulário principal. Descartados: misturar
pesquisa externa e execução de comandos arbitrários, e usar correspondência
aproximada como autorização para selecionar cidade homônima.
Impacto esperado: teclado utilizável com localização explicitamente escolhida.
Validação: seleção por teclado, exigência de ID exato no backend e erro de
catálogo. A homepage teve timeout na nova consulta; utilizou-se o manual
acessível, não uma inspeção interativa inventada.

## 3. CRM/detalhe: Attio Records

Fonte: https://attio.com/help/reference/managing-your-data/records/create-and-view-records

Problema: fatos comerciais eram revisados dentro do modal que cria buscas.
O manual organiza informações e atividades em um registro e descreve prévia
sem abandonar a lista. Adaptação: revisão comercial na ficha existente, aba
Análise, com fatos atuais, edição explícita, justificativa e versionamento.
Editar o cadastro preserva a ficha de origem abaixo do diálogo. Descartados:
novas abas de e-mail, objetos e colaboração que duplicariam mecanismos locais.
Impacto: revisão disponível independentemente da busca que encontrou a empresa.
Validação: salvar e recarregar fatos; testes backend de propriedade do registro,
versão obsoleta e reclassificação. Não foi avaliada uma conta real do Attio.

## 4. CRM/lista: Attio Table Views

Fonte: https://attio.com/help/reference/managing-your-data/views/create-and-manage-table-views

Problema: resultados duplicados entre um relatório de busca e o Radar.
A documentação distingue atributos persistidos de colunas, ordenação e filtros
de visualização, e oferece prévia de registro a partir da tabela.
Adaptação: os resultados da busca entregam o registro canônico; grupos filtram
a mesma base usada pela lista e pelo mapa. Descartadas edição em massa e grade
de planilha completa: não são necessárias para qualificar esta oportunidade.
Impacto: uma alteração comercial pode atualizar a classificação sem criar
outra avaliação. Validação: filtro de descartadas e recuperação dos registros
do job; consultas históricas, snapshots e monitores exercitados por testes de compatibilidade.

## 5. Componente: Spell Keyboard Shortcuts

Fonte: https://spell.sh/docs/kbd

Problema: atalhos visuais podem contaminar o nome acessível da ação.
A página documenta símbolos, indicação de tecla ativa e listener opcional.
Adaptação: manter `/` como pista discreta junto ao CTA; ação e nome acessível
continuam “Buscar empresas”. O atalho ignora entrada de texto já em edição.
Descartados instalação de uma nova biblioteca e efeitos que simulam teclas
pressionadas sem função. Impacto: descoberta do atalho sem poluir leitura.
Validação: a primeira execução encontrou “Buscar empresas /”; corrigido
`aria-hidden` no `kbd`, mantendo o botão acessível e o atalho real.

## 6. Microinteração: Unlumen Animated List

Fonte: https://ui.unlumen.com/components/animated-list

Problema: atualizações de resultados podem desorientar durante leitura.
A documentação demonstra identidade estável dos itens e entrada/saída animada,
com inserções no início e limite curto de itens no exemplo.
Adaptação adotada: conservar IDs de registros e contadores de estado, sem
recriar registros visuais a cada polling. Descartados empilhamento automático,
limite de oito itens e animação contínua de chegada: o Radar guarda resultados
persistentes e a ordenação comercial precisa permanecer compreensível.
Impacto: atualização previsível em vez de distração. Validação de movimento
fica limitada ao comportamento local com reduced motion; não se afirma
equivalência de timing com a demonstração externa. Nenhuma biblioteca adicionada.

## 7. Composição/identidade: Linear por Refero Styles

Fonte: https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1

Problema: superfícies escuras sem hierarquia ou com decoração excessiva.
A referência descreve valores escuros próximos, tipografia Inter e bordas
discretas. Adaptação: formulário contido, espaçamento consistente, histórico
em linhas e separadores, usando tokens já presentes. Descartados cores de
acento da referência, títulos de marketing e escalas de hero.
Impacto: pesquisa integrada ao workspace ScoutLIQ, preservando crimson.
Validação: capturas em desktop/mobile, overflow e contraste; pesquisa documental
não substitui avaliação visual local. Não é cópia de um dashboard Linear.

## 8. Composição/identidade: Ramp por Refero Styles

Fonte: https://styles.refero.design/style/b38702a0-75ab-474c-9106-00b624535825

Problema: destaque semântico diluído por cards e acentos em excesso.
A referência apresenta base quase monocromática, superfícies separadas por
bordas e um único acento concentrado em ações/estados.
Adaptação: ações primárias em crimson e fatos comerciais organizados em
pares rótulo/valor, sem cards iguais para cada atributo. Descartados amarelo
neon, fonte proprietária e espaçamento de landing page.
Impacto: hierarquia por função, não por efeito. Validação: componente de
revisão em duas colunas no desktop e uma no mobile, acompanhada da regressão
das superfícies existentes descrita em VALIDATION-v1.37.md. O conteúdo consultado é uma interpretação
de estilo da Refero, não a engenharia original da Ramp.

## Contrato geográfico complementar

Documentação técnica oficial:
https://apidocs.geoapify.com/docs/geocoding/address-autocomplete/
e https://apidocs.geoapify.com/docs/places/

Foi verificado o uso de categorias de hamburgueria e filtro `place` para área
selecionada. A implementação recusa substituição silenciosa por raio quando o
adaptador não tem a capacidade necessária. Consulta documental e testes
controlados não comprovam cobertura real, qualidade comercial ou custos reais.

## Validação e implementação

As referências orientaram o formulário compacto, histórico/progresso no Radar,
a ficha contextual e o ritmo de listas. BEFORE-AFTER-v1.37.md e
SIMPLIFICATION-v1.37.md registram a aplicação. VALIDATION-v1.37.md distingue
implementação local de homologação externa. Não foi copiada uma tela de referência.
