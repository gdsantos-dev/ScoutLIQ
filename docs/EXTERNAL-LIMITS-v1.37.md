# Limitações externas e estados — v1.37

## Implementado e testado localmente

Busca unificada, adaptadores de compatibilidade, critérios preservados, mapa, catálogo validado, custo/cache, worker e monitores existentes, persistência, cancelamento/recuperação, revisão rápida auditada, modais, idiomas afetados, migração aditiva e pacotes verificáveis. Provedores dos testes são fixtures explícitas.

## Implementado, sem homologação externa nesta execução

Geoapify/IBGE em rede real; cobertura e fronteiras por bairro/cidade/estado/país; interpretação semântica com modelo pago; Gmail OAuth/API e replies reais; implantação, HTTPS/proxy/cookies em domínio público, PostgreSQL e Docker. A documentação consultada não substitui um teste com credenciais autorizadas.

## Capacidade parcial por projeto

Fallback IBGE só resolve municípios brasileiros. Fontes sem capacidade de limite administrativo/área são recusadas. País/estado selecionável não implica levantamento completo. A meta não é preenchida artificialmente. Geoapify, OSM e fontes de investigação conservam limitações de setor, paginação, cobertura e orçamento.

Qualidade comercial real exige casos ORLIQ revisados e resultados de vendas. Fixtures verificam funcionamento, não precisão comercial real ou conversão. Score 3.0 não foi recalibrado automaticamente.

## Bloqueado por insumo externo

Homologação de serviços externos e envios reais exige credenciais válidas, configuração, condições de contato verificadas e autorização explícita. Nenhum envio comercial real foi executado. Não houve deploy nem alteração da instalação pessoal.

## Fora da evidência local

Safari/iOS físicos, teclado virtual real, touchpad físico, leitor de tela humano, múltiplas réplicas em produção e desempenho em rede móvel. Chrome com viewports/toque emulados e axe não certifica esses ambientes. Rate limiting de autenticação herdado é local ao processo; governança de catálogo/worker/semântica é persistente. O operador deve validar topologia e rate limiting compartilhado antes de escalar réplicas.
