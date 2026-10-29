# Validação — ScoutLIQ v1.35.0

Base exclusiva: FULL v1.34.0, SHA256 `46f5b86e0ab08441a73843648a0a3e49d6027b1c930b64186ab1a6c623e34582`. Manifesto original com 271 arquivos conferido antes da extração. Desenvolvimento isolado em `work/v1.35.0/ScoutLIQ`; código e banco operacionais não atualizados. O ambiente de ferramentas `.venv` recebeu cryptography para QA. Sem redesign do Prompt 3.

## Evidência local

| Verificação | Resultado | Evidência reproduzível |
|---|---|---|
| Backend completo final | **265 aprovados**, incluindo os 204 herdados | `artifacts/pytest-release-v135.txt`; pytest 330,53s |
| Comunicação/migração após preservar aviso de cobertura parcial | **29 aprovados** | `artifacts/communication-final.txt` |
| Score padrão vs código do ZIP exato | **175 resultados completos iguais** | `scripts/verify_score_baseline.py`, `artifacts/score-baseline-v135.json` |
| Frontend unitário | **23 aprovados / 7 arquivos** | `artifacts/frontend-tests-v135-final.txt` |
| TypeScript / Vite / tipos E2E | Aprovados | `artifacts/build-v135-final.txt`, `artifacts/typecheck-e2e-v135-final.txt` |
| Supervisor real | Prontidão; queda do worker encerra web; restart; shutdown coordenado | `artifacts/process-acceptance-v135.txt` |
| Migrações | 024/025 preservam campos canônicos; 026 preserva todas as tabelas anteriores; recusa apagar ledger tentado | testes de migração e `artifacts/migration-026.txt` |
| Dependências Python | Zero vulnerabilidades conhecidas | `artifacts/pip-audit-v135.json` |
| Dependências npm, incluindo dev | Zero vulnerabilidades conhecidas | `artifacts/npm-audit-v135.json` |
| Navegador build final | **40 E2E distintos aprovados em três grupos**, sem falhas nos grupos finais | `e2e-legacy-v135.txt` (33 / 8,8min), `e2e-intelligence-v135.txt` (6 / 1,6min), `e2e-communication-v135.txt` (1 / 34,3s), todos em artifacts |
| FULL/PATCH | 307 fontes + manifesto, 62 entradas de PATCH, 52 arquivos backend/migração idênticos à base; aplicação e recusa de conflito/reaplicação verificadas | `scripts/verify_release.py`, `artifacts/release-validation.json`; somas dos ZIPs em `release/SHA256SUMS.txt` |

Os logs brutos e screenshots ficam na pasta local artifacts e são excluídos dos pacotes de código; este relatório e os testes/fontes entram no FULL. Os testes usam dados sintéticos e provedores controlados. Números de testes não representam volume de leads reais, qualidade comercial ou homologação externa.

A rodada final usou hosts locais separados por grupo para respeitar o rate limit de login. Comunicação passou com HTTP/DB/UI reais locais e worker em processo separado, substituindo somente a API Gmail. Há verificação axe, teclado, reduced motion e reflow em 320/390/768/1440 nas novas funções; a regressão herdada cobre também 375/393/430/1920. Screenshots finais de comunicação mobile/desktop foram inspecionados. Nenhum teste foi enfraquecido para obter aprovação.

## Cobertura funcional e limites

| Recurso | Implementação / validação | Homologação externa / pendência |
|---|---|---|
| Casos revisados, importação, histórico e exportação | Implementado / testado localmente | Casos ORLIQ reais ainda não fornecidos |
| Métricas, splits e comparação de critérios | Implementado / testado localmente | Ganho de precisão/conversão não medido |
| Sugestão, aprovação e rollback do Score 3.0 | Implementado / testado localmente | Sem recalibração automática; limite 5.000 Leads por transação |
| Outbox, identidade, aprovação, orçamento, recovery | Implementado / testado localmente | Não promete exatamente uma vez; incerto nunca reenvia automaticamente |
| OAuth/API Gmail, cifra, refresh, reconnect/revoke | Implementado / testado com provedor controlado | **Bloqueado para homologação real:** cliente/credenciais/conta/autorização específica não fornecidos |
| Respostas, dedup, cursor, associação e próxima ação | Implementado / testado localmente | Google real não homologado; histórico antigo limitado e ambiguidades sem vínculo |
| Condição de contato/jurisdição | Implementado como revisão humana documentada e guardas | Não certifica legalidade; habilitação de mercado exige responsabilidade externa |
| SPF/DKIM/DMARC | **Parcial:** registro manual da revisão | Diagnóstico automático não implementado |
| WhatsApp Business | **Parcial:** contrato compartilhado e canal fechado | Adapter Cloud/templates/janela/webhooks ainda não implementados |
| Deploy / HTTPS / PostgreSQL / Docker / dispositivos físicos | Não homologados nesta execução | Exigem ambiente e validação próprios |

## Falhas encontradas e corrigidas

- Migração 025 inicialmente usava recriação de Leads para remover coluna, disparando CASCADE de dependentes em downgrade. Substituída por DROP COLUMN nativo; roundtrips conferem tabelas/campos, evidências, rascunhos, FK e integridade. Não classificar as primeiras falhas como baseline conhecida.
- Controle de sincronização no navegador atualizava checkbox apenas após HTTP. Corrigido para refletir a ação e reconciliar com o estado do servidor em sucesso/erro.
- Inspeção visual mobile encontrou checkboxes comprimidos pela regra de largura automática. Dimensão/área legível corrigida no componente compartilhado; E2E verifica geometria.
- Primeira fixture Gmail de QA tinha chave sintética com tamanho incorreto; servidor recusou iniciar. Corrigida a fixture, sem enfraquecer validação de cifra.
- Reexecução de QA reutilizava destinatário sem informar versão da política já existente. Teste passou a usar destinatário único por execução; controle de versão permaneceu intacto.
- Durante P0.3, uma execução conjunta de E2E atingiu rate limit de login após testes anteriores. Grupos isolados/reinício somente da QA resolveram; proteção de login não foi reduzida.

Warnings conhecidos: duas depreciações Python (Starlette/httpx e anyio), aviso herdado de chunk de mapa maior que 500KB e NO_COLOR/FORCE_COLOR no runner. Sem alegação de performance, acessibilidade de leitor de tela ou comportamento em dispositivos físicos a partir desses testes.

## Conclusão comercial

Nenhum envio real, credencial operacional, conta de terceiros ou caso privado foi usado. Zero amostra comercial real revisada foi importada. A versão permite medir divergência e executar o fluxo controlado; não há evidência de que suas decisões ou conversão comercial melhoraram no mundo real. Ver COMMERCIAL-MATRIX-v1.35.md para o protocolo de avaliação e GMAIL-v1.35.md para condições de homologação.
