# Patch 1.19.1 → 1.20.0

Patch exclusivo para o ZIP `ScoutLIQ-v1.19.1-campaigns-typescript-hotfix-full.zip`. Não substitui banco, `.env`, volume ou credenciais. Não adiciona migrações. Alembic continua em `018`.

Extraia o patch em uma pasta separada. Faça backup do banco e configuração de qualquer instalação real. Com a aplicação parada, execute:

```powershell
python apply_release_patch.py --target "C:\caminho\ScoutLIQ"
```

O comando apenas verifica os hashes de todos os arquivos afetados. Havendo edição local ou base diferente, recusa a aplicação antes de alterar arquivos. Depois da verificação:

```powershell
python apply_release_patch.py --target "C:\caminho\ScoutLIQ" --apply
cd "C:\caminho\ScoutLIQ\frontend"
npm ci
npm run build
```

Reinicie usando as mesmas variáveis e volume. Recarregue abas abertas, pois os nomes dos assets mudaram. Backend, contratos, modelos e migrations são idênticos aos da base. O build não vem no ZIP: gere-o no destino.

Os arquivos anteriores ficam em `.scoutliq-backups/<data UTC>/`. Em falha durante a cópia, o script restaura as operações concluídas. Preserve esse backup até homologar. Para voltar, pare a aplicação, restaure as fontes do backup e remova somente arquivos com `before_sha256: null` no manifesto. Gere novamente o build anterior. O banco não requer rollback.

`PATCH-MANIFEST.json` descreve adições, alterações e remoções. `after_sha256: null` significa remoção de fonte obsoleta; cada remoção também exige o hash da base. Não aplique manualmente por cima de outra versão. Havendo customizações, compare o pacote completo em um diretório novo antes de integrar.
