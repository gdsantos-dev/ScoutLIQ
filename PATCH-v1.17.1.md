# ScoutLIQ v1.17.1 — Railway TypeScript hotfix

Hotfix de compilação da v1.17.0.

- Corrige o tipo persistido do `scope` do Radar para aceitar `region`, `radius`, `bounds` e `polygon`.
- Alinha a assinatura persistida com `RadarSearchResponse["scope"]` e `RadarSearchInput["scope"]`.
- Nenhuma migration nova e nenhuma alteração de banco.
- Nenhuma regra funcional do Radar foi alterada; o hotfix apenas converge o contrato TypeScript já usado pela pesquisa territorial.
