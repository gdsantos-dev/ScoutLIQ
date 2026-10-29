# Atualizações do ScoutLIQ

O repositório privado https://github.com/gdsantos-dev/ScoutLIQ é a fonte principal. `main` representa a versão integrada. Nenhuma atualização deve começar de um ZIP antigo ou de uma cópia sem conferir o remoto.

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/descricao-da-alteracao
# Implementar e validar a alteração autorizada.
git status --short
git diff --check
git add caminho/dos/arquivos-revisados
git diff --cached
git commit -m "fix: descreva a mudança concreta"
git push -u origin codex/descricao-da-alteracao
```

Abra um pull request para `main`, descrevendo problema, mudança, testes e limites. Não sobrescrever histórico remoto nem usar force push na branch principal. Essa é a política de trabalho; não há promessa de proteção de branch imposta pelo plano do GitHub.

Antes de publicar, verificar que o índice não contém secrets, dados pessoais, `.env`, bancos, backups, logs de runtime ou dependências instaladas. Apenas `.env.example` com segredos vazios é versionado. Credenciais nunca devem aparecer em commits, mensagens ou logs. Os recibos textuais de release já importados são históricos; binários ZIP e runtime ficam fora do Git.

Preservar arquitetura, dados, autenticação, autorização, Score Engine e migrações. Mudanças funcionais exigem testes adequados; mudanças de UX exigem verificação real de navegador/mobile. Diferenciar validação local de homologação externa. Não realizar deploy ou envio comercial como consequência de um push.

Use HANDOFF.md e os documentos da versão atual para retomar. Atualize esses registros quando o escopo mudar. Gere pacotes a partir de um commit identificado, se solicitados.
