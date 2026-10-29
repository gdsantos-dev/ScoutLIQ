# Checkpoint — v1.38.3-dev

## Local de retomada

Pasta integrada: `work/v1.38.3-dev/ScoutLIQ`. Não retomar a implementação a partir da v1.38.2, pois ela é apenas a base de comparação. Não repetir os mecanismos das versões anteriores.

Leia primeiro `VALIDATION-v1.38.3-dev.md`, depois `INVESTIGATION-v1.38.3-dev.md` e os recibos de `release/`. Os arquivos-fonte do pacote podem ser conferidos com `scripts/verify_investigation_package.py` depois da extração. Os ZIPs são identificados pelo `SHA256SUMS.txt` externo.

## Implementação

- Política, preferências, entrada, classificação e fases: `backend/investigation.py`.
- Executor e recuperação compartilhados: `backend/research_worker.py`; reserva de consultas: `backend/consumption.py`.
- Entradas transacionais: `_persist_discovery` em `backend/main.py` e confirmação em `backend/absorption.py`.
- Deduplicação com investigação da Busca: `backend/smart_search.py`.
- Persistência: campos aditivos em `backend/models.py`, revisão `030_progressive_investigation.py`.
- Interface: `Radar.tsx`, `AbsorptionDialog.tsx`, `InvestigationSettings.tsx`, Configurações e estilos existentes.
- Provas: `test_progressive_investigation.py`, `test_investigation_migration.py`, `frontend/e2e/investigation.spec.ts` e regressões históricas.

## Próximo ciclo

Nenhum deploy foi solicitado ou realizado. Não habilitar a automação em uma instalação pessoal sem decisão do operador. Nenhuma autorização comercial de envio foi concedida; não enviar e-mail/WhatsApp para Leads.

As pendências externas são: homologar configuração e quotas reais dos provedores; repetir upgrade e concorrência em PostgreSQL do ambiente-alvo; verificar infraestrutura HTTPS, cookies, CORS e segredos de produção; atualizar auditoria de vulnerabilidades antes de publicação; medir qualidade comercial com casos revisados e resultados reais da ORLIQ. Não inferir taxa de conversão a partir das fixtures.

As 029 e 030 preservam históricos que não devem ser descartados por downgrade forçado. Para reversão depois de uso, seguir a política de backup consistente descrita em `INSTALL-v1.38.3-dev.md`.

O próximo trabalho funcional deve partir das evidências e limites documentados, sem novo redesign nem criação de um segundo executor ou pontuação concorrente.
