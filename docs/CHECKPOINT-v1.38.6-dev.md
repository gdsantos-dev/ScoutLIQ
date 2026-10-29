# Checkpoint — v1.38.6-dev

Código e validação local concluídos na cópia work/v1.38.6-dev/ScoutLIQ. Base exclusiva v1.38.5-dev FULL SHA256 7310028178df19e949295990cd81bba4037f5c04dd94f1602d463564fb8bfb22. Não reiniciar a integração a partir de versão antiga.

551 backend, 27 frontend unitários, 75 E2E/17 suítes, TypeScript e Vite aprovados. 62 fontes canônicas preservadas por hash. Revisão 032 mantida, sem banco novo nem alterações de esquema. Implementação principal: backend/operational_intelligence.py; integração: frontend/src/pages/Intelligence.tsx e components/CommercialHistory.tsx. Contratos: METRICS-v1.38.6-dev.md.

Antes de usar uma cópia distribuída, verificar os recibos em release e o FULL extraído com scripts/verify_operations_package.py. Caso uma execução seja interrompida durante empacotamento, repetir scripts/package_operations_v1386.py com o FULL v1.38.5 verificado e executar scripts/verify_operations_clean_install.py. Não usar o manifesto anterior como recibo da versão nova. Nenhuma aprovação de deploy/envio está implícita.

Pendências de cobertura deliberadas: eventos antigos ausentes, elegibilidade de buscas legadas, índices de classificação sem validade, consumo não instrumentado fora do worker, desfechos sem data/snapshot. Não reconstruir retroativamente. Esforço humano/custo monetário e economia permanecem indisponíveis até existir instrumentação/tarifa confiável. Qualidade comercial real depende de casos humanos e resultados de operação; fixtures não a homologam.

Homologação externa ainda necessária para produção/PostgreSQL/provedores/dispositivos físicos. Próximo ciclo deve partir deste FULL e respeitar estes limites. Não alterar pesos do Score, implantar ou iniciar redesenho sem escopo novo do usuário.
