# Patch 1.28.0 → 1.29.0

Este patch adiciona a área **Integrações** e o contrato ORLIQ Bridge v1. Não cria migration nem altera schema de banco.

## Aplicação recomendada

1. Faça backup da instalação atual.
2. Confirme que a origem é exatamente a v1.28.0.
3. Execute o patch em dry-run primeiro.
4. Aplique somente se a verificação de hashes passar.
5. Preserve `.env`, banco, diretórios de dados e artefatos de runtime.
6. Não execute migration por causa desta versão.
7. Após aplicar, abra **Menu do workspace → Integrações**.
8. Gere um pacote Ecossistema ORLIQ e um pacote DashLIQ Financeiro e confira as contagens antes de usar os arquivos fora do ScoutLIQ.

A v1.29.0 não sincroniza dados automaticamente. O arquivo é um handoff explícito e local.
