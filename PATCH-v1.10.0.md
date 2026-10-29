# ScoutLIQ v1.10.0 — Commercial History, Smart Lists & Saved Searches

Quarta e última parcela da primeira fase de evolução do ScoutLIQ.

## 1. Histórico comercial real

- a ficha da empresa passa a exibir uma linha do tempo comercial persistida no backend;
- é possível registrar WhatsApp, ligação, e-mail, reunião, proposta, resposta e anotação;
- mudanças de etapa, próxima ação, fechamento de venda e reabertura após exclusão de venda entram automaticamente no histórico;
- contatos manuais atualizam `last_contact_at`, usado pelas listas inteligentes;
- abrir WhatsApp não registra contato automaticamente: o histórico só recebe ações efetivamente registradas.

## 2. Listas inteligentes

O Radar ganha visões derivadas dos próprios leads, sem duplicar dados:

- Alta prioridade;
- Sem site;
- Só no Radar;
- Pipeline ativo;
- Ação para hoje;
- Ação atrasada;
- Sem contato há 7 dias;
- Novos esta semana.

Leads antigos já presentes no Pipeline recebem `pipeline_added_at` a partir de `created_at` durante a migração para manter a regra de inatividade utilizável.

## 3. Buscas salvas

- uma busca executada no Radar pode ser salva com nome próprio;
- localização, nicho, escopo e raio ficam persistidos;
- a busca pode ser executada novamente com um clique;
- o ScoutLIQ compara os IDs atuais com a execução anterior e mostra quantos estabelecimentos novos apareceram;
- limite inicial: 30 buscas salvas por workspace;
- exclusão ocorre dentro da interface, sem prompt nativo do navegador.

## Persistência

A migration `011_commercial_history_saved_searches.py` adiciona:

- `leads.pipeline_added_at`;
- `leads.last_contact_at`;
- tabela `lead_activities`;
- tabela `radar_saved_searches`.

A exportação passa para `schema_version: 6` e inclui `lead_activities` e `radar_saved_searches`.

## Atualização

Depois de substituir os arquivos, execute:

```bash
python -m alembic upgrade head
```

Depois compile o frontend normalmente antes do deploy.

## Validação

- suíte backend: 63 testes;
- migration aplicada em banco SQLite temporário durante a suíte;
- testes novos cobrem histórico manual + automático, `last_contact_at`, busca salva, detecção de novos resultados, conflito de versão e exportação;
- TS/TSX alterado validado sintaticamente com TypeScript;
- CSS validado sem erros de parsing;
- o build completo do frontend não foi executado neste ambiente porque as dependências npm não estão disponíveis integralmente em cache.
