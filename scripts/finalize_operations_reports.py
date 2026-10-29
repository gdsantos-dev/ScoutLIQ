"""Generate delivery documentation only after recorded local checks pass."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile
from build_release import source_files

ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'artifacts'
D=ROOT/'docs'
Q=D/'qa-v1.38.6-dev'


def read(path):
    data=path.read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')


def main():
    assert '551 passed' in read(A/'backend-final.txt')
    unit=re.sub(r'\x1b\[[0-9;]*m','',read(A/'frontend-unit-final.txt'))
    assert re.search(r'27\s+passed',unit)
    assert not read(A/'typescript-final.txt').strip()
    assert not read(A/'typescript-e2e-final.txt').strip()
    assert 'built in' in read(A/'frontend-build-final.txt')
    suites=[]
    for group in ('complete','operations','commercial','followup'):
        result=json.loads(read(A/f'browser-group-{group}.json'))
        assert all(r['exit_code']==0 for r in result),group
        suites.extend(result)
    assert len(suites)==17
    counts={}
    for suite in suites:
        log=read(A/f"e2e-{suite['suite']}-release.txt")
        matches=re.findall(r'(\d+) passed',log)
        assert matches,suite
        counts[suite['suite']]=int(matches[-1])
    assert sum(counts.values())==75,counts
    volumes=[json.loads(read(A/f'operational-volume-{n}.json')) for n in (1000,10000)]
    preserved=json.loads(read(A/'preserved-engines.json'))
    assert preserved['count']==62 and preserved['all_match_base']
    for name,sha in preserved['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    captures=['operations-desktop.png','operations-efficiency-desktop.png','operations-390.png','operations-320.png']
    evidence=['backend-final.txt','frontend-unit-final.txt','typescript-final.txt','typescript-e2e-final.txt','frontend-build-final.txt',
        'operational-volume-1000.json','operational-volume-10000.json','base-verification.json','preserved-engines.json']
    evidence += [f'e2e-{s["suite"]}-release.txt' for s in suites]
    evidence += [f'browser-group-{g}.json' for g in ('complete','operations','commercial','followup')]
    Q.mkdir(exist_ok=True)
    for name in evidence+captures:
        (Q/name).write_bytes((A/name).read_bytes())
    validation=dict(version='1.38.6-dev',status='validated_locally',backend=551,new_backend=37,frontend_unit=27,e2e=sum(counts.values()),
        suites=counts,typescript=True,typescript_e2e=True,vite=True,volumes=volumes,preserved_files=62,migration='032',new_migration=None,
        real_sends=0,real_provider_calls=0,deployment=False,production_database_touched=False,production_ready=False,
        partial=['Historical discovery/eligibility','Current classification cache coverage','Worker consumption coverage','Commercial outcome histories'],
        unavailable=['Human effort','Minutes saved','Monetary cost','Hypothetical requests avoided','Time until available for review'],
        not_homologated=['PostgreSQL repeatable read','Production deployment','Real providers','Physical mobile devices','Safari','Screen readers'],
        warnings=['Existing Starlette/httpx and anyio deprecations','Existing Vite map chunk size warning'])
    (Q/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    volume_table='\n'.join(f"| {r['companies']:,} | {r['queries']} | {r['seconds']} s | {r['response_bytes']} |" for r in volumes)
    text=f'''# Validação — v1.38.6-dev

Status: implementação validada localmente em dados sintéticos. Não é homologação externa nem autorização de deploy.

| Verificação | Resultado |
|---|---|
| Backend completo | 551 testes aprovados, incluindo 37 novos |
| Frontend unitário | 27 testes em 8 arquivos aprovados |
| TypeScript aplicação/E2E | Aprovados |
| Vite | Build concluído |
| E2E | 75 testes aprovados em 17 suítes |
| Preservação | 62 fontes/migrações canônicas idênticas ao FULL base |
| Migração | 032 mantida, nenhuma 033 necessária |

## Volume observado

| Empresas | Consultas SQL | Tempo local | Bytes da resposta |
|---|---|---|---|
{volume_table}

Cada cenário possui também uma atividade e uma revisão por empresa. Os 15 comandos incluem autenticação e início do snapshot. A resposta é agregada, sem histórico individual no navegador. Tempos variam com carga do computador e não são SLA. Não houve chamadas reais a provedores.

## Cobertura dos 22 critérios do ciclo

1–3. Identidade única, repetição, origem e múltiplas fontes: `test_sources_deduplicate_same_company_without_merging_homonyms`.
4–6. Histórico parcial, ausência e demo: `test_missing_identity_and_partial_legacy_history_are_not_invented`, `test_empty_data_has_unknown_rates_and_no_fabricated_alerts`, `test_demo_is_excluded_from_every_linked_relation`.
7–10. Retomada, falhas/custos, fusos/DST e denominadores: testes interrupted_resumed, provider_calls, calendar_window e completion_events.
11–14. Rascunho não é contato, declaração/aceitação, associação ambígua e desfecho sem história: testes approved_draft, manual_accepted, reply_requires_traceable, unassociated_message, reply_before_new_acceptance e behavior_never_synthesizes.
15–16. Amostras pequenas e diagnósticos factuais: sources_deduplicate e observed_diagnostics.
17–20. Propriedade, concorrência, idempotência, volume e ausência de efeitos: ownership_on_every_join, concurrent_read, volume_bounded_queries, safety_ceiling, authentication_required, filters_are_closed e rate_limiter. Leitura concorrente não emite INSERT/UPDATE/DELETE nem chama Score/assess.
21. Score e motores preservados por SHA256; testes de regressão e de leitura mantêm versões, critérios e estágio.
22. Suítes históricas completas, incluindo Busca Geral/Unificada, absorção, autonomia, experiência, workflow, redesenho existente, aprendizado, inteligência, comunicação, investigação, fila e acompanhamento.

## Navegador e correções verificadas

Novo E2E usa o endpoint real e registros canônicos sintéticos. Cobre desktop, conta vazia, filtros, proveniência, ausência de requisições por histórico de empresa, falha/retry, redução de movimento, tabelas navegáveis por teclado e larguras 390/320 px. Axe não encontrou violações nas áreas novas cobertas pelos testes; isso não equivale a homologação com leitor de tela.

As duas primeiras execuções encontraram seletores de teste inadequados ao combobox nativo. O seletor passou a usar papel/nome acessíveis e selectOption. A execução seguinte encontrou overflow real no mobile; o grid recebeu coluna minmax(0,1fr) e filhos com min-width:0. A execução final passou após rebuild. Capturas finais estão em qa-v1.38.6-dev.

## Segurança e limites

Revisão do escopo: endpoint autenticado, filtros Literal fechados, proprietário conferido em todos os joins, ORM parametrizado, rate limit 30/min, projeções limitadas, snapshot transacional sem mutação e sem chamadas externas. Não retorna corpos, credenciais, destinatários ou listas de IDs. Campos de agrupamento usam escape do React. Nenhuma dependência nova. Autenticação/CSRF/CORS/cookies, destinatários/opt-out, worker, webhooks e APIs administrativas existentes não foram modificados. Não foram adicionados uploads, SQL/NoSQL dinâmico, eval, comandos com input ou caminhos externos.

Continuam parciais: histórico de descoberta antiga, elegibilidade fora da absorção, classificação quando o índice está vencido/ausente, consumo fora do worker e resultados comerciais incompletos. Permanecem indisponíveis: esforço humano, economia de minutos, custo monetário, chamadas hipotéticas evitadas e tempo até disponibilidade para revisão.

Não homologados: PostgreSQL, provedores reais, produção, HTTPS de implantação, dispositivos físicos, Safari e leitores de tela. Nenhum envio real, deploy ou alteração de banco de produção. Avisos existentes: deprecações Starlette/httpx/anyio e tamanho do chunk de mapas do Vite.

## Evidências e pacotes

Logs e resultados estruturados: qa-v1.38.6-dev/validation.json e arquivos adjacentes. Os recibos externos em release comprovam CRC/hashes, PATCH dry-run, conflito recusado, equivalência com FULL, preservação de runtime, recusa de reaplicação e rollback de fontes. A verificação de extração limpa é registrada em CLEAN-INSTALL-VALIDATION.json após o empacotamento; não é presumida por este documento.
'''
    (D/'VALIDATION-v1.38.6-dev.md').write_text(text,encoding='utf-8')
    (D/'CHECKPOINT-v1.38.6-dev.md').write_text('''# Checkpoint — v1.38.6-dev

Código e validação local concluídos na cópia work/v1.38.6-dev/ScoutLIQ. Base exclusiva v1.38.5-dev FULL SHA256 7310028178df19e949295990cd81bba4037f5c04dd94f1602d463564fb8bfb22. Não reiniciar a integração a partir de versão antiga.

551 backend, 27 frontend unitários, 75 E2E/17 suítes, TypeScript e Vite aprovados. 62 fontes canônicas preservadas por hash. Revisão 032 mantida, sem banco novo nem alterações de esquema. Implementação principal: backend/operational_intelligence.py; integração: frontend/src/pages/Intelligence.tsx e components/CommercialHistory.tsx. Contratos: METRICS-v1.38.6-dev.md.

Antes de usar uma cópia distribuída, verificar os recibos em release e o FULL extraído com scripts/verify_operations_package.py. Caso uma execução seja interrompida durante empacotamento, repetir scripts/package_operations_v1386.py com o FULL v1.38.5 verificado e executar scripts/verify_operations_clean_install.py. Não usar o manifesto anterior como recibo da versão nova. Nenhuma aprovação de deploy/envio está implícita.

Pendências de cobertura deliberadas: eventos antigos ausentes, elegibilidade de buscas legadas, índices de classificação sem validade, consumo não instrumentado fora do worker, desfechos sem data/snapshot. Não reconstruir retroativamente. Esforço humano/custo monetário e economia permanecem indisponíveis até existir instrumentação/tarifa confiável. Qualidade comercial real depende de casos humanos e resultados de operação; fixtures não a homologam.

Homologação externa ainda necessária para produção/PostgreSQL/provedores/dispositivos físicos. Próximo ciclo deve partir deste FULL e respeitar estes limites. Não alterar pesos do Score, implantar ou iniciar redesenho sem escopo novo do usuário.
''',encoding='utf-8')
    with ZipFile(ROOT.parent.parent/'v1.38.5-dev/ScoutLIQ/release/ScoutLIQ-v1.38.5-dev-FULL.zip') as z:
        baseline={n.removeprefix('ScoutLIQ/'):z.read(n) for n in z.namelist() if not n.endswith('/')}
    files=source_files();files['DEV-OVERLAY-MANIFEST.json']=(ROOT/'DEV-OVERLAY-MANIFEST.json').read_bytes()
    names=sorted(n for n,b in files.items() if baseline.get(n)!=b)
    (D/'CHANGED-FILES-v1.38.6-dev.md').write_text('# Arquivos alterados — v1.38.6-dev\n\nComparação com FULL v1.38.5-dev. Recibos e manifesto final são gerados no empacotamento; PATCH-MANIFEST.json é a lista definitiva.\n\n'+''.join(f'- `{n}`\n' for n in names)+'- `docs/CHANGED-FILES-v1.38.6-dev.md`\n',encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
