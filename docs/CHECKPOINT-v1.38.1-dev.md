# Checkpoint — v1.38.1-dev

Pasta: work/v1.38.1-dev/ScoutLIQ. Base exclusiva: work/v1.38-dev/ScoutLIQ/release/ScoutLIQ-v1.38-dev-integration-FULL.zip; SHA256 f66a5097486760825f3f3ba1b33c5cab7036a81bd1ce282010b414afe916232b.

Implementação concluída para o ciclo Busca Unificada com exploração geral/nicho opcional. Validação: 373 backend, 23 unitários frontend, 31 E2E, build e tipagem aprovados. O teste focal de tags OSM inválidas também passou. Fontes protegidas e migrações conferidas; head 028. Não retomar pela instalação histórica nem reimplementar Absorção/P0.1.

Para verificar a entrega, conferir RELEASE-MANIFEST.json, release/SHA256SUMS.txt e release/PACKAGE-VALIDATION.json. O script scripts/package_general_v1381.py reproduz os pacotes e a verificação em instalações descartáveis. Relatório: docs/VALIDATION-v1.38.1-dev.md; contrato/changelog/instalação têm o mesmo sufixo de versão.

Não há implementação local pendente deste ciclo. O próximo trabalho é homologação externa autorizada de cobertura e avaliação comercial real, não a repetição dos testes sintéticos. Não há autorização para deploy, migração de produção ou envio comercial. A documentação histórica conserva suas limitações; este checkpoint não certifica produção.
