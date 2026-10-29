# ScoutLIQ v1.9.0 — Radar → Pipeline & Next Action

Terceira parcela da primeira fase de evolução do ScoutLIQ.

## O que mudou

### 1. Salvar oportunidade direto do Radar

- cada resultado fora do Pipeline recebe a ação **Salvar oportunidade**;
- o registro existente é promovido ao Pipeline, sem criar cópia;
- score, pesquisa web, auditoria, contatos e origem permanecem no mesmo lead;
- a ficha usa a mesma ação quando a empresa ainda não está no Pipeline.

### 2. Radar e Pipeline no mesmo estado

- ao salvar no Radar, `in_pipeline` é atualizado no mesmo registro;
- filtros e badges do Radar reagem ao estado do Pipeline;
- mover etapas continua usando versionamento otimista do registro;
- o Pipeline mantém somente oportunidades salvas, sem uma segunda base paralela.

### 3. Próxima ação

- oportunidades ativas do Pipeline podem registrar uma ação de até 180 caracteres;
- a data é opcional;
- datas passadas não podem ser cadastradas;
- ações vencidas permanecem visíveis e recebem estado de atraso no Pipeline;
- cards são ordenados primeiro por prazo da próxima ação e depois pelo índice da oportunidade;
- ao marcar uma oportunidade como **Perdida** ou registrar uma venda, a próxima ação é limpa automaticamente.

## Persistência

A migration `010_pipeline_next_action.py` adiciona a `leads`:

- `next_action`;
- `next_action_on`;
- índice por `next_action_on`.

O schema de exportação passa para a versão 5.

## Atualização

Depois de substituir os arquivos, execute:

```bash
python -m alembic upgrade head
```

Em seguida compile o frontend normalmente antes do deploy.

## Validação

- suíte backend: 61 testes;
- migration aplicada em banco SQLite temporário durante a suíte;
- teste de próxima ação cobre bloqueio fora do Pipeline, persistência, normalização, limpeza e conflito de versão.
