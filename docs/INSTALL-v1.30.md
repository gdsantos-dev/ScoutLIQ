# Instalação e atualização — ScoutLIQ 1.30.0

Entrega de código-fonte FULL e PATCH para o ZIP exato 1.29.0. Nenhum banco, .env real, node_modules, segredo ou dado de produção integra os arquivos.

## Instalação FULL

Extraia `ScoutLIQ/` em uma pasta nova. Requer Python 3.12+ e Node compatível com Vite 7 (a validação usou Node 24). Use os comandos abaixo a partir da raiz do projeto, ativando o venv conforme seu sistema:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
```

Edite o .env: defina um banco e credenciais próprios. Não reutilize credenciais de teste; mantenha DEMO_SEED=false para operação. Configure a origem exata. Antes de iniciar o backend:

```powershell
npm run build --prefix frontend
python -m alembic upgrade head
python scripts/start.py
```

O frontend precisa ser compilado antes do backend: o código herdado monta `frontend/dist/assets` na inicialização. A revisão final é 019. O desenvolvimento/teste local usa SQLite isolado; nenhuma homologação de PostgreSQL foi realizada.

## PATCH sobre v1.29.0

1. Pare a aplicação e faça backup consistente do SQLite com `scripts/backup.py`, além do .env e do código atual. Não migre dados reais enquanto estiver sem backup restaurável.
2. Extraia o PATCH fora da instalação. Execute o preflight, apontando para a pasta que contém backend/main.py:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

3. O aplicador verifica versão e hashes dos arquivos afetados, preserva dados/.env e cria backup dos fontes alterados. Se houver personalização nos arquivos afetados, ele recusa antes de escrever. Não aplique sobre v1.20 ou outras bases.
4. Na instalação atualizada, execute `pip install -r requirements.lock`, `npm ci --prefix frontend`, build, `alembic upgrade head` e reinicie. Valide login, `/api/health`, dados existentes e a aba Operação da ficha.

## Reversão

`alembic downgrade 018` foi testado em banco descartável, seguido por upgrade. Ele preserva os registros anteriores de leads, mas **remove evidências, rascunhos e preferências novos**. Para reversão operacional que preserve integralmente o estado, restaure o backup compatível e os fontes anteriores. Não use downgrade destrutivo como rotina em produção.

## Usar a fatia entregue

Abra uma empresa e selecione **Operação**. Importe uma pesquisa já realizada ou registre uma observação com URL. Revise classificação e justificativa. Selecione evidências confirmadas/válidas, canal, idioma e destinatário. Prepare, edite e aprove a mensagem com referência da autorização do contato. Recarregar a página preserva o rascunho.

Aprovação não significa envio. A integração oficial ainda não foi implementada. A API de dispatch responde 503 sem transmitir dados. O assistente manual anterior permanece disponível e seu registro é identificado como manual. Registrar uma resposta pausa os rascunhos pendentes dos dois canais da oportunidade; não existem sequências automáticas novas nesta versão.

## Testes e configuração

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm run test --prefix frontend
npm run typecheck:e2e --prefix frontend
python scripts/start_e2e.py
# Em outro terminal:
npm run test:e2e --prefix frontend -- e2e/workflow.spec.ts
```

`start_e2e.py` cria banco local com dados fictícios e credenciais exclusivamente de teste na porta 8001. Não a exponha em rede pública. Se houver EPERM no Windows, use TEMP/TMP dentro da pasta de trabalho e confira permissões; não redirecione os testes ao banco operacional.

Não foram acrescentadas variáveis de OAuth, WhatsApp ou Gmail sem implementação correspondente. A configuração de pesquisa/conta já existente está no .env.example e README. Deploy/HTTPS real, provedores, política de retenção e validação por mercado continuam pendentes conforme AUDIT-v1.30.md e SECURITY-GATE-v1.30.md.
