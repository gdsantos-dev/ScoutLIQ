# ScoutLIQ v1.10.1 — Railway TypeScript build hotfix

Hotfix de consistência do frontend para deploy de produção.

- Mantém `timezone` na interface do Pipeline, alinhada ao `App.tsx`.
- Atualiza o fixture de `opportunity.test.ts` para os campos persistidos introduzidos na v1.9.0: `pipeline_added_at` e `last_contact_at`.
- Alinha a versão do pacote npm e a versão exibida pela interface para 1.10.1.
- Deve ser aplicado como release completo quando o deploy atual estiver com arquivos de versões diferentes.
