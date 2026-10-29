# Instalação local — v1.38.7-dev

Pacote de desenvolvimento validado localmente; não constitui deploy ou homologação de produção. Dependências permanecem as da v1.38.6. O FULL contém fontes, testes, migrações e documentação, sem `.env`, banco, credenciais, `node_modules`, `dist` ou dados pessoais.

## Base e PATCH

O PATCH exige a instalação correspondente ao FULL v1.38.6-dev, SHA256 `dbf392f49ae3c13e699b7b345743f164774953717747f39c06b136e1e1a04f79`. Ele valida hashes antes de qualquer escrita e recusa customizações conflitantes. Não substitua alterações próprias para forçar a aplicação.

1. Preserve backup do banco e dos arquivos de runtime. Pare o worker e o serviço web durante upgrade/migração.
2. Confira `release/SHA256SUMS.txt` da distribuição. Esse recibo externo lista os hashes dos ZIPs. Dentro do FULL, o arquivo homônimo lista hashes das fontes; os dois têm escopos diferentes por evitar autorreferência.
3. Extraia o PATCH numa pasta separada e execute a simulação:

```powershell
python apply_release_patch.py --target "CAMINHO_DA_INSTALACAO/ScoutLIQ"
```

4. Após validar o relatório, aplique:

```powershell
python apply_release_patch.py --target "CAMINHO_DA_INSTALACAO/ScoutLIQ" --apply
```

O aplicador conserva runtime e cria backup das fontes afetadas. Reaplicar é recusado. Ele não migra o banco automaticamente.

## Dependências, migração e build

Use o ambiente Python e o processo de instalação documentados no README. Na raiz da instalação:

```powershell
python -m pip install -r requirements.lock
python -m alembic upgrade head
```

A head esperada é `033`, sobre `032`. O upgrade cria quatro tabelas de metadados e um índice, preservando dados antigos. Na pasta `frontend`:

```powershell
npm ci
npm run build
```

Inicie web/worker pelo processo existente. O planejamento exige `RESEARCH_EXECUTION_MODE=worker`, limites globais válidos e pesquisas salvas configuradas e ativas. Abrir a interface não consulta provedores. Configurar o plano não o ativa: revise a prévia e confirme explicitamente.

## Verificação e recuperação

Na extração limpa do FULL, antes de modificar fontes:

```powershell
python scripts/verify_planning_package.py --root .
```

O verificador confere o manifesto e os recibos internos. O resultado da verificação independente dos arquivos distribuídos fica em `release/PACKAGE-VALIDATION.json`; a validação adicional em extração limpa fica em `release/CLEAN-INSTALL-VALIDATION.json`.

Pausar interrompe jobs do plano e mantém sua coordenação; desativar libera as recorrências originais previamente autorizadas. Antes de reverter fontes, pause o plano e pare o worker. Reverter fontes não deve remover dados da revisão 033. O downgrade recusa apagar planejamento existente; para restaurar integralmente uma versão anterior, utilize backup compatível do banco e das fontes. Não faça downgrade destrutivo para contornar a proteção.

Os testes locais usam SQLite e adaptadores sintéticos. Provedores reais, PostgreSQL, produção, HTTPS e dispositivos físicos exigem homologação própria, sem autorizar contatos comerciais.
