# Validação — ScoutLIQ v1.36.0

Data: 19/10/2026. Base exclusiva: FULL v1.35.0, SHA256 `2e5bac34cbe21dd40224991fa874a58655b5863847b1ac0efcdc3e8cf51981f6`. Trabalho em cópia nova; instalação pessoal não modificada. Head 026, nenhuma migração nova; **74 arquivos de backend/migrações idênticos à base**.

## Resultados locais

| Verificação | Resultado | Evidência em artifacts |
|---|---|---|
| Backend completo | **265 passaram**, 2 avisos de depreciação, 227,62 s | pytest-v136-final.txt |
| Frontend unitário final | **23 passaram**, 7 arquivos | unit-v136-final.txt |
| TypeScript / Vite / tipos E2E | Aprovados | build-v136-final.txt, e2e-typecheck-v136-final.txt |
| Navegação, gestão e estados herdados | **25 cenários distintos passaram** | e2e-workspace-v136-final.txt (contém também experience e uma falha de seletor corrigida abaixo) |
| Busca e ficha herdadas | **8 passaram** | e2e-core-v136-final.txt |
| Autonomia, inteligência e aprendizado | **6 passaram** | e2e-advanced-v136.txt |
| Comunicação controlada, worker e resposta/CRM | **1 passou** em fixture limpa | e2e-communication-v136-clean.txt |
| Experiência nova | **3 passaram**: responsividade/etapas, memória/mapa sob demanda e entradas EN/ES | e2e-experience-v136-final.txt |
| Busca após resumo/traduções finais | **3 passaram**, repetição dos mesmos cenários, não somados novamente | e2e-search-v136-final.txt |
| Dependências | Zero vulnerabilidades conhecidas reportadas por npm audit (inclui dev) e pip-audit do lock | npm-audit-v136.json, pip-audit-v136.json |
| Preservação | 74 fontes backend/migrações byte a byte iguais | backend-preservation-v136.json |
| FULL / PATCH / Score | Verificação por manifesto, aplicação em cópia e conflitos; equivalência do Score contra arquivo exato | release-validation.json, score-baseline-v136.json |

**43 cenários E2E distintos aprovados no conjunto final**, preservando os 40 herdados e acrescentando 3. Não significa que todos foram executados em um único processo. Os 25 de redesign, os 8 de core, 6 advanced e 1 communication passaram; os três testes novos passaram no build final. A alteração final de resumo/tradução da busca foi novamente coberta pelos três E2E de busca, além de build/unit/typecheck. Não houve alteração posterior de lógica de produção após esses testes.

Os logs brutos ficam em artifacts e em um ZIP separado de evidências; não integram a instalação. Capturas antes/depois selecionadas integram docs/experience-v136. Dados são sintéticos; adaptadores externos são controlados. Nenhum envio Gmail/WhatsApp real ou nova autorização operacional.

## Falhas encontradas e corrigidas

- Em 768 px, a sidebar estreitava páginas herdadas com tabelas/controles. Navegação compacta passou a cobrir até 1024 px, sem mascarar overflow global. Reflow e ficha repetidos com sucesso.
- Consolidação de CSS removeu regras do editor mobile ligadas ao antigo shell. Repostas com escopo do editor e tokens, sem blur; o fluxo de criação/fechamento voltou a passar.
- Dois grupos Playwright compartilhavam outputDir e colidiam nos arquivos de trace (ENOENT ao fechar contexto). Diretórios separados; cenários repetidos passaram.
- Novo teste do mapa usava um atributo inexistente. Corrigido para `data-ready=true`, observado no DOM; a asserção de carregamento sob demanda passou.
- Teste legado de comunicação fixava a porta 8016 no worker. Agora usa E2E_PORT/origem. Repetição sobre fila residual reagendou mensagem por intervalo entre tentativas. Usada fixture nova em 8023; proteção mantida, cenário aprovado.
- Primeiros testes sandbox falharam por acesso a TEMP/cache ou localhost. Repetidos com diretório temporário local e execução autorizada. Não considerados sucessos anteriores.
- Uma rodada inicial de navegador coincidiu com regeneração do build e encontrou chunks removidos. Todos os resultados finais ocorreram com build estável.

## Estado de entrega e limites

| Área | Estado |
|---|---|
| Shell, navegação, tokens, Radar, etapas da ficha, busca progressiva | Implementado e testado localmente |
| Comunicação/rotinas, descoberta de funções, gestão existente | Refinado e testado localmente; serviços v1.35 preservados |
| CSS | Consolidado nas superfícies substituídas; **parcial** fora delas. Não alegar conversão completa dos globais em módulos. |
| PT/EN/ES | Novas entradas, etapas e rótulos de busca traduzidos/testados. **Parcial** nos textos herdados de inteligência, revisão, comunicação e mensagens de servidor. Não declarar aplicativo inteiro trilíngue. |
| Evidência/qualificação | Mesmos Score e evidências; nenhuma melhoria de precisão ou conversão real inferida de teste técnico |
| Acessibilidade | Axe/teclado/foco/reflow/reduced motion locais aprovados nos cenários. Leitor de tela real e dispositivos físicos não homologados |
| Gmail/OAuth e respostas | Provedor controlado local. Homologação real bloqueada pela ausência de credenciais/conta/autorização específicas |
| WhatsApp | Contrato compartilhado preservado; adapter Cloud permanece pendência herdada. Remake não implementa integração nova |
| Deploy / HTTPS / Docker / PostgreSQL / Safari | Não executados ou homologados nesta entrega |
| Usabilidade comercial | Revisão crítica e capturas feitas; operação ORLIQ real, acompanhamento prolongado e qualidade de oportunidades não medidos |

Esta é uma consolidação funcional da camada de experiência. Não representa aprovação externa de toda a missão nem remake integral de cada formulário legado. Continuidade precisa das pendências: CHECKPOINT-v1.36.md. Segurança: SECURITY-v1.36.md. Comparação crítica: EXPERIENCE-v1.36.md.
