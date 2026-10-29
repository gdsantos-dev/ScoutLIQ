"""Scoped observations and interpretation; the existing score remains authoritative."""
import json
import time
import hashlib
from sqlalchemy import select
from .opportunity_models import OpportunityEvidence

ANALYZER = 'html-checks-v2'
# Vocabulary is tied to actual research.py predicates, never a translated free-form assertion.
CHECKS = {
 'context_services': ('content', 'o HTML contém um link rotulado de serviços, produtos ou cardápio', 'the HTML contains a link labelled services, products or menu', 'el HTML contiene un enlace de servicios, productos o menú'),
 'context_contact': ('contact', 'o HTML contém um link de contato válido ou formulário', 'the HTML contains a valid contact link or form', 'el HTML contiene un enlace de contacto válido o formulario'),
 'context_booking': ('content', 'o HTML contém um sinal reconhecido de agendamento', 'the HTML contains a recognized booking signal', 'el HTML contiene una señal de reservas reconocida'),
 'https': ('security', 'a URL final usa HTTPS', 'the final URL uses HTTPS', 'la URL final utiliza HTTPS'),
 'viewport': ('mobile', 'o HTML contém meta viewport', 'the HTML contains a viewport meta tag', 'el HTML contiene una etiqueta meta viewport'),
 'title': ('discovery', 'o título da página atende ao critério do analisador', 'the page title meets the analyzer criteria', 'el título cumple el criterio del analizador'),
 'description': ('discovery', 'a meta description tem pelo menos 30 caracteres', 'the meta description has at least 30 characters', 'la meta description tiene al menos 30 caracteres'),
 'schema': ('discovery', 'o HTML contém dados estruturados', 'the HTML contains structured data', 'el HTML contiene datos estructurados'),
 'contact': ('contact', 'o HTML contém um canal de contato reconhecido', 'the HTML contains a recognized contact channel', 'el HTML contiene un canal de contacto reconocido'),
 'speed': ('performance', 'a resposta levou até 2,5 segundos neste teste', 'the response took at most 2.5 seconds in this test', 'la respuesta tardó como máximo 2,5 segundos en esta prueba'),
}
TTL = {'performance': 3, 'security': 7, 'contact': 14, 'mobile': 30, 'discovery': 30, 'content': 30, 'general': 14}

def observation(key, state, locale='pt-BR'):
    index = {'pt-BR': 1, 'en-US': 2, 'es': 3}[locale]
    predicate = CHECKS[key][index]
    if locale == 'en-US':
        return f'In the inspected page, this check {"passed" if state == "pass" else "did not pass"}: {predicate}.'
    if locale == 'es':
        return f'En la página analizada, esta comprobación {"se cumplió" if state == "pass" else "no se cumplió"}: {predicate}.'
    return f'Na página analisada, este critério {"foi atendido" if state == "pass" else "não foi atendido"}: {predicate}.'

def reconcile(db, lead, research):
    from .opportunity_workflow import activity
    # Failed collection is not a refutation or a reason to erase earlier facts.
    if research.status != 'confirmed' or not research.website_url:
        return 0
    rows = list(db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.lead_id == lead.id,
        OpportunityEvidence.user_id == lead.user_id)).all())
    added = 0
    for check in json.loads(research.checks_json or '[]')[:20]:
        key, state = check.get('key'), check.get('state')
        if key not in CHECKS or state not in ('pass', 'warn', 'fail'): continue
        source_url = check.get('source_url', research.website_url) if key.startswith('context_') else research.website_url
        source_key = key + ':' + hashlib.sha256(source_url.encode()).hexdigest()[:16] if key.startswith('context_') else key
        old = next((e for e in rows if e.observation_key == key and e.source_url == source_url and e.relation == 'current'), None)
        legacy = next((e for e in rows if e.source_key == f'research:{research.checked_at}:{key}' and not e.observation_key), None)
        if legacy:
            activity(db, lead, 'evidence_scope_migrated', 'Observação legada recebeu escopo explícito e exige nova revisão.',
                evidence_id=legacy.id, previous_statement=legacy.statement, previous_classification=legacy.classification)
            legacy.observation_key, legacy.observation_state, legacy.category = key, state, CHECKS[key][0]
            legacy.statement, legacy.classification, legacy.analyzer_version = observation(key, state), 'probable', ANALYZER
            legacy.scope, legacy.research_id = 'Somente o critério e a página analisados.', research.id
            old = legacy
        if old and old.observed_at >= research.checked_at: continue
        if old and old.observation_state == state:
            old.verified_at = research.checked_at
            old.observed_at = research.checked_at
            old.valid_until = research.checked_at + TTL[old.category] * 86400
            activity(db, lead, 'evidence_reobserved', 'Critério observado novamente com o mesmo resultado.', evidence_id=old.id, research_id=research.id)
            continue
        if len(rows) >= 200:
            if old:
                old.relation = 'superseded'
                activity(db, lead, 'evidence_contradicted_at_capacity',
                    'Nova pesquisa diverge; observação anterior retirada de uso. Limite de evidências atingido.',
                    evidence_id=old.id, previous_statement=old.statement,
                    statement=observation(key, state), research_id=research.id)
            continue
        category = CHECKS[key][0]
        item = OpportunityEvidence(user_id=lead.user_id, lead_id=lead.id,
            source_key=f'research:{research.checked_at}:{source_key}', statement=observation(key, state),
            source_url=source_url, scope='Somente a página e o instante analisados; não comprova uma deficiência em todo o site nem conversão comercial.',
            method='research_snapshot', classification='probable', observed_at=research.checked_at,
            verified_at=research.checked_at, valid_until=research.checked_at + TTL[category] * 86400,
            category=category, research_id=research.id, observation_key=key, observation_state=state,
            analyzer_version=ANALYZER, related_id=old.id if old else None)
        db.add(item); db.flush()
        if old:
            old.relation = 'superseded'
            activity(db, lead, 'evidence_contradicted', 'Nova observação diverge do resultado anterior; revisão necessária.',
                evidence_id=item.id, previous_id=old.id, previous_statement=old.statement, statement=item.statement)
        else:
            activity(db, lead, 'evidence_added', 'Observação técnica incorporada para revisão.', evidence_id=item.id, statement=item.statement)
        rows.append(item); added += 1
    return added

def interpretation(lead, evidence, existing_score):
    current = [e for e in evidence if e['relation'] == 'current']
    useful = [e for e in current if e['classification'] == 'confirmed' and not e['stale']]
    gaps = [e for e in useful if e['observation_state'] in ('fail', 'warn') or e['category'] == 'content']
    required = ['security', 'mobile', 'discovery', 'contact', 'performance', 'content']
    investigated = sorted({e['category'] for e in current if e['category'] in required and (e['method'] == 'research_snapshot' or e['verified_at'])})
    missing = [c for c in required if c not in investigated]
    conflicts = [e for e in current if e['related_id'] and e['classification'] != 'confirmed']
    services = {'security': 'Correção técnica', 'mobile': 'Avaliação e ajustes de responsividade',
                'discovery': 'Melhorias de conteúdo e SEO técnico', 'contact': 'Melhoria dos canais de contato',
                'performance': 'Diagnóstico de desempenho', 'content': 'Melhorias de conteúdo e navegação'}
    recommendations = [{'service': services[e['category']], 'evidence_ids': [e['id']], 'reason': e['statement']}
                       for e in gaps if e['category'] in services]
    diagnosis = (gaps[0]['statement'] if gaps else
                 'Nenhuma necessidade comercial sustentada pelas evidências atuais.')
    reliability = 'divergent' if conflicts else 'reviewed' if useful else 'indeterminate'
    return {'diagnosis': diagnosis, 'evidence_ids': [e['id'] for e in gaps], 'services': recommendations,
        'coverage': {'investigated': investigated, 'required': required, 'missing': missing},
        'reliability': {'state': reliability, 'reason': 'Revisão do operador; não é certificação técnica independente.' if useful else 'Faltam observações atuais revisadas.',
                        'expired': sum(e['stale'] for e in current), 'conflicts': len(conflicts)},
        'priority': existing_score['value'], 'factors': [r['label'] for r in existing_score['reasons'][:4]]}

def decide(lead, evidence, drafts, insight, research, activities, batch_active=False):
    """One reusable server-side decision, with command and explicit preconditions."""
    now = int(time.time())
    def action(key, label, reason, command, ids=None, blockers=None, state='ready'):
        return {'id': key, 'type': key, 'label': label, 'reason': reason, 'command': command,
                'evidence_ids': ids or [], 'state': state, 'preconditions': ['Oportunidade ativa', 'Revisão humana antes de contato'],
                'blockers': blockers or [], 'requires_approval': key == 'review_message', 'as_of': now}
    if lead.contact_blocked or lead.stage in ('won', 'lost') or lead.demo:
        return action('record_result', 'Consultar histórico', 'Contato suspenso ou oportunidade encerrada.', 'history')
    if lead.stage in ('replied', 'negotiating') or any(a.kind == 'reply' for a in activities):
        return action('record_activity', 'Registrar próxima atividade', 'Há uma resposta; combine e registre a continuidade da conversa.', 'activity')
    if lead.next_action:
        return action('scheduled_activity', 'Revisar atividade agendada', lead.next_action, 'activity')
    if batch_active:
        return action('research_running', 'Atualizar progresso', 'A investigação está na fila persistente do servidor; o worker deve estar ativo.', 'refresh', state='pending')
    if not evidence:
        return action('investigate', 'Iniciar investigação', 'Ainda não há observações para sustentar um diagnóstico.', 'investigate')
    if insight['reliability']['conflicts'] or not insight['evidence_ids']:
        return action('verify_evidence', 'Revisar evidências', 'Confirme escopo, atualidade e necessidade antes de sugerir uma abordagem.', 'evidence')
    if drafts:
        draft = drafts[0]
        if draft.get('content_blocker'):
            return action('review_message', 'Revisar mensagem', draft['content_blocker'], 'draft', draft['evidence_ids'])
        return action('check_eligibility', 'Revisar condição de contato', draft['send_blocker'], 'policy', draft['evidence_ids'], [draft['send_blocker']])
    if not (lead.whatsapp or lead.phone or lead.contact):
        return action('identify_contact', 'Definir destinatário', 'Não há contato registrado. Verifique o destinatário antes de preparar a mensagem.', 'prepare', insight['evidence_ids'])
    return action('prepare_outreach', 'Preparar abordagem', 'Use as observações revisadas e confirme um destinatário para o canal escolhido.', 'prepare', insight['evidence_ids'])
