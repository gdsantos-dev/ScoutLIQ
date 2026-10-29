# Patch 1.27.0 → 1.28.0

Este patch adiciona a área de Inteligência do histórico comercial e seus utilitários de análise. Não cria migration nem altera schema de banco.

## Aplicação recomendada

1. Faça backup da instalação atual.
2. Confirme que a origem é exatamente a v1.27.0.
3. Execute o patch em dry-run primeiro.
4. Aplique somente se a verificação de hashes passar.
5. Preserve `.env`, banco, diretórios de dados e artefatos de runtime.
6. Não execute migration por causa desta versão.
7. Após aplicar, valide a nova rota **Gerir clientes → Histórico** em desktop e mobile.
8. Compare uma base com ganhos e perdas conhecidos e confirme se as contagens refletem o histórico registrado.

A análise é descritiva. Nenhum indicador da v1.28.0 deve ser interpretado como probabilidade de fechamento.
