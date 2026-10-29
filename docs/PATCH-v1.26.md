# Patch 1.25.0 → 1.26.0

Este patch adiciona a camada de Execução Comercial e a nova área **Ações**. Ele não cria migration e não altera backend ou schema de banco.

## Aplicação recomendada

1. Faça backup da instalação atual.
2. Confirme que a origem é exatamente a v1.25.0 antes de aplicar o patch.
3. Execute o patch em dry-run primeiro.
4. Aplique somente se a verificação de hashes passar.
5. Preserve `.env`, banco, diretórios de dados e artefatos de runtime.
6. Não execute migration por causa desta versão.
7. Após aplicar, valide Ações em desktop e mobile, principalmente abrir contatos externos, registrar interação, remarcar e concluir próxima ação.

O pacote incremental contém apenas os arquivos alterados entre v1.25.0 e v1.26.0, mais o aplicador e o manifesto de hashes.
