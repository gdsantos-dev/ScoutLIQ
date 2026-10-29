"""Emit delivery evidence only after all local verification gates pass."""
import hashlib,json,re
from pathlib import Path
from zipfile import ZipFile
from build_release import source_files
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'artifacts';D=ROOT/'docs';Q=D/'qa-v1.38.7-dev'

def read(path):
    data=path.read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')

def main():
    backend=read(A/'backend-final.txt')
    assert '592 passed' in backend and not re.search(r'\d+ failed|\d+ errors',backend)
    unit=re.sub(r'\x1b\[[0-9;]*m','',read(A/'frontend-unit-final.txt'))
    assert re.search(r'27\s+passed',unit)
    assert not read(A/'typescript-final.txt').strip()
    assert not read(A/'typescript-e2e-final.txt').strip()
    assert 'built in' in read(A/'frontend-build-final.txt')
    groups=('complete','operations','commercial','followup','planning')
    suites=[]
    for group in groups:
        data=json.loads(read(A/f'browser-group-{group}.json'))
        assert all(r['exit_code']==0 for r in data),group
        suites.extend(data)
    assert len(suites)==18
    counts={s['suite']:int(re.findall(r'(\d+) passed',read(A/f"e2e-{s['suite']}-release.txt"))[-1]) for s in suites}
    assert sum(counts.values())==77,counts
    preserved=json.loads(read(A/'preserved-engines.json'))
    assert preserved['all_match_base'] and preserved['count']==61
    for name,sha in preserved['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    volumes=[json.loads(read(A/f'planning-volume-{size}.json')) for size in (1000,10000)]
    captures=['planning-desktop.png','planning-progress-desktop.png','planning-390.png','planning-320.png']
    evidence=['backend-final.txt','frontend-unit-final.txt','typescript-final.txt','typescript-e2e-final.txt','frontend-build-final.txt',
        'planning-volume-1000.json','planning-volume-10000.json','base-verification.json','preserved-engines.json']
    evidence += [f'e2e-{s["suite"]}-release.txt' for s in suites]
    evidence += [f'browser-group-{g}.json' for g in groups]
    Q.mkdir(exist_ok=True)
    for name in [*captures,*evidence]: (Q/name).write_bytes((A/name).read_bytes())
    validation=dict(version='1.38.7-dev',status='validated_locally',backend=592,new_backend=41,frontend_unit=27,e2e=77,suites=counts,
        typescript=True,typescript_e2e=True,vite=True,volumes=volumes,preserved_files=61,migration='033',base_migration='032',
        real_sends=0,real_provider_calls=0,deployment=False,production_database_touched=False,production_ready=False,
        partial=['Historical discard coverage before 033','History after explicit canonical deletion','Historical timezones after account changes'],
        unavailable=['Verified monetary pricing','Commercial profitability inference'],
        not_homologated=['PostgreSQL','Production deployment','Real providers','Physical mobile devices','Safari','Screen readers'],
        warnings=['Existing Starlette/httpx and anyio deprecations','Existing Vite map chunk size warning'])
    (Q/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    rows='\n'.join(f"| {v['companies']:,} | {v['queries']} | {v['seconds']} s | 0 |" for v in volumes)
    (D/'VALIDATION-v1.38.7-dev.md').write_text(f'''# Validação — v1.38.7-dev

Status: implementado e validado localmente em bancos isolados e adaptadores sintéticos. Sem homologação externa ou autorização de deploy.

| Verificação | Resultado |
|---|---|
| Backend completo | 592 testes aprovados, 41 novos |
| Frontend unitário | 27 testes aprovados |
| TypeScript aplicação/E2E | Aprovados |
| Vite | Build concluído |
| E2E | 77 testes aprovados em 18 suítes |
| Preservação | 61 fontes/migrações canônicas idênticas ao FULL base |
| Migração | 033 sobre 032; preservação e recusa de downgrade destrutivo testadas |

## Volume

| Empresas | Consultas de progresso | Tempo local | Provedores |
|---|---|---|---|
{rows}

A consulta usa agregações SQL sem carregar a lista de Leads. A contagem de consultas permanece constante. Tempos locais não são SLA nem homologação PostgreSQL. O scheduler não chama o relatório completo de Inteligência.

## Cobertura dos 27 critérios obrigatórios

| Critérios | Evidência |
|---|---|
| 1–2. Desativado e consentimento | `test_disabled_creation_and_explicit_current_preview` e E2E de autorização |
| 3. Metas 25/50/75/100 | `test_configurable_goal_and_first_canonical_incorporation`, parametrizado |
| 4–5. Unicidade e múltiplas origens | `test_manual_and_absorption_origins_count_once_demo_and_existing_do_not`; crédito explicitamente vinculado |
| 6–8. Busca geral, direcionada e dois locais | `test_two_authorized_locations_general_search_priority_and_neutral_fallback` |
| 9–10. Reencontro e nenhum resultado | Testes de duas pesquisas sobre a mesma identidade e `test_no_new_results_exhausts_only_authorized_search` |
| 11–14. Cooldown, limites, meta e orçamento | `test_daily_limit_and_cooldown`, `test_goal_reached_by_other_ingress_prevents_new_work`, `test_operation_budget_reserved_atomically_for_plan` |
| 15–16. Fonte e busca indisponíveis | `test_unavailable_provider_and_global_limit_do_not_create_job`, `test_existing_search_blocks_plan_without_cancelling_it` |
| 17–18. Concorrência e reinício | `test_two_workers_one_plan_one_canonical_job_and_restart_recovery`; reabertura de sessão e recuperação de lease |
| 19–20. Pausa, retomada, desativação e histórico | `test_pause_fences_inflight_resume_disable_keep_history_and_saved_config`; E2E com página fechada |
| 21–22. Sugestões sem evidência e com fatos | Testes de sugestões sem dados e backlog observado, com período/população/contagem |
| 23. Isolamento | DTO, ownership, CSRF, autenticação, duas contas e progresso separado |
| 24. Integridade das rotinas/jobs | Regressão de autonomia, caminho único `schedule_saved`, hashes de preservação |
| 25. Ausência de envio | Somente discovery/research nos planos; nenhum hook em comunicação; adapters simulados e regressão de comunicação |
| 26. Inteligência Operacional | Suíte backend e E2E `operations` preservadas |
| 27. Regressão histórica | Backend completo e 17 suítes anteriores de navegador |

Cobertura adicional: resultados acima do limite do adaptador, descarte sem crédito, DST, fairness entre contas, prevenção de loops sem orçamento e recusa de exclusão que apagaria vínculos do orçamento diário.

## Evidência visual

`qa-v1.38.7-dev/planning-desktop.png`, `planning-progress-desktop.png`, `planning-390.png` e `planning-320.png`. Chromium local, 1440 px desktop e 390/320 px mobile, redução de movimento, teclado, erro/retry e Axe WCAG A/AA. Não substitui testes em dispositivo físico, Safari ou leitor de tela. Ajustes finais de checkbox e remoção explícita de pesquisa fora da lista são cobertos no E2E final de planejamento; não houve remake.

## Segurança e limites

Entrada validada no backend, DTO com campos permitidos, ownership de pesquisas/plano e joins de crédito, ORM parametrizado, autenticação/CSRF existentes, rate limits e autorização por prévia atual. Fencing e reservas persistentes impedem duplicidade e ultrapassagem de orçamento; nenhum provedor é chamado ao abrir a interface. Conteúdo é renderizado por React sem HTML arbitrário.

Não foram adicionados upload, webhook, login, pagamento, segredo no frontend ou caminho de execução de comandos externos. Autenticação, sessões, headers, CORS, opt-outs e comunicação existentes foram preservados e submetidos à regressão. Dependências não mudaram. Não foi efetuada nova auditoria de CVEs em serviço externo nem revisão de produção: esta entrega não é deploy.

## Limitações e estados

- **Implementado/testado localmente:** plano, consentimento, execução no worker existente, limites, progresso, sugestões, histórico e UI.
- **Parcial:** descartes históricos sem observação antes de 033; histórico recalculado após exclusões; comparação de dias após alteração de fuso. Esses dados não geram otimização automática.
- **Delimitado:** um plano por conta; até 20 pesquisas; máximo de uma execução por pesquisa/dia; cooldown mínimo 24 h; janela no mesmo dia; histórico até 366 dias/200 decisões exibidas; opções até 200 pesquisas com aviso.
- **Sem dados verificáveis:** custo monetário e lucratividade. Não estimados.
- **Não homologado externamente:** PostgreSQL, provedores reais, produção/HTTPS, Safari, dispositivos físicos e leitores de tela.

Não houve envio comercial, uso de cota externa, deploy ou alteração de banco de produção. Permanecem avisos já existentes de depreciação Starlette/anyio e tamanho do chunk de mapa do Vite.

## Distribuição

Os recibos externos `release/PACKAGE-VALIDATION.json` e `release/CLEAN-INSTALL-VALIDATION.json` registram verificação de hashes, equivalência PATCH/FULL, proteção de runtime, recusa de conflito/reaplicação, rollback de fontes e teste em extração limpa. O relatório de fonte não se autoatribui os hashes dos ZIPs. Consulte os recibos após o empacotamento.
''',encoding='utf-8')
    (D/'CHECKPOINT-v1.38.7-dev.md').write_text('''# Checkpoint — v1.38.7-dev

Base v1.38.6-dev FULL verificada por hash/CRC; revisão 032. Implementação local na cópia isolada `work/v1.38.7-dev/ScoutLIQ`, nova revisão 033. Não reiniciar o desenvolvimento da feature nem reimplementar scheduler/worker.

Código: `backend/prospecting.py`, `backend/prospecting_models.py`, migração 033 e hooks pequenos em routines, consumption, smart_search e main. UI em `frontend/src/components/ProspectingPlan.tsx`, integrada em Automações. Arquitetura, contratos e limitações nos documentos desta versão.

Validação funcional: 592 backend, 27 unitários frontend, TypeScript/Vite e 77 E2E aprovados. Evidências em `docs/qa-v1.38.7-dev`. Comparação por hashes preserva 61 fontes/migrações canônicas.

Gate final de distribuição: executar `scripts/package_planning_v1387.py --base ../../v1.38.6-dev/ScoutLIQ/release/ScoutLIQ-v1.38.6-dev-FULL.zip` e `scripts/verify_planning_clean_install.py`; conferir os recibos externos PACKAGE-VALIDATION e CLEAN-INSTALL-VALIDATION em release. A existência dos recibos aprovados e os hashes dos ZIPs são o checkpoint verificável de entrega, não este texto isolado.

Retomada futura: usar o FULL v1.38.7-dev identificado em `release/SHA256SUMS.txt`, validar manifesto e recibos, preservar runtime e aplicar migração 033 conforme INSTALL. Não considerar homologados provedores/PostgreSQL/produção/dispositivos físicos. Não autorizar envios a partir do plano. Homologações externas exigem ambiente e credenciais próprios e autorização correspondente.
''',encoding='utf-8')
    base=ROOT.parent.parent/'v1.38.6-dev/ScoutLIQ/release/ScoutLIQ-v1.38.6-dev-FULL.zip'
    with ZipFile(base) as z: baseline={n.removeprefix('ScoutLIQ/'):z.read(n) for n in z.namelist() if not n.endswith('/')}
    sources=source_files();sources['DEV-OVERLAY-MANIFEST.json']=(ROOT/'DEV-OVERLAY-MANIFEST.json').read_bytes()
    names=[n for n in sorted(sources) if sources[n]!=baseline.get(n) and n!='docs/CHANGED-FILES-v1.38.7-dev.md']
    names.append('docs/CHANGED-FILES-v1.38.7-dev.md')
    (D/'CHANGED-FILES-v1.38.7-dev.md').write_text('# Arquivos alterados — v1.38.7-dev\n\nComparação com o FULL v1.38.6-dev. Manifesto/recibos de distribuição são regenerados pelo empacotador.\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n',encoding='utf-8')
    print(json.dumps(validation,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
