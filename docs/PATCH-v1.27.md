# Patch 1.26.0 → 1.27.0

Este patch adiciona Outreach assistido + templates na área Ações. Não cria migration e não altera backend ou schema de banco.

## Aplicação recomendada

1. Faça backup da instalação atual.
2. Confirme que a origem é exatamente a v1.26.0.
3. Execute o patch em dry-run primeiro.
4. Aplique somente se a verificação de hashes passar.
5. Preserve `.env`, banco, diretórios de dados e artefatos de runtime.
6. Não execute migration por causa desta versão.
7. Após aplicar, valide criação/edição de templates, troca de canal, preenchimento de variáveis, abertura de WhatsApp/e-mail e registro manual do envio.

Templates personalizados são mantidos no `localStorage` do navegador e isolados pelo ID da conta.
