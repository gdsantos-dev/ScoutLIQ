"""Identity evidence for staging; this is not a commercial score or a merge engine."""
from urllib.parse import urlsplit
from .absorption_input import key

def digits(value):return ''.join(c for c in str(value or '') if c.isdigit())
def domain(value):
    try:return (urlsplit(value or '').hostname or '').lower().removeprefix('www.')
    except ValueError:return ''
def compare(a,b):
    a=dict(a);b=dict(b)
    name=key(a.get('name'))==key(b.get('name')) and bool(key(a.get('name')))
    city=key(a.get('city'))==key(b.get('city')) and bool(key(a.get('city')))
    if a.get('country') and b.get('country') and a['country']!=b['country']:return 'distinct','Países diferentes.'
    if a.get('city') and b.get('city') and not city:return 'distinct','Municípios diferentes.'
    near=False;far=False
    if all(r.get(f) is not None for r in [a,b] for f in ['latitude','longitude']):
        near=abs(float(a['latitude'])-float(b['latitude']))<=.0001 and abs(float(a['longitude'])-float(b['longitude']))<=.0001
        far=abs(float(a['latitude'])-float(b['latitude']))>.002 or abs(float(a['longitude'])-float(b['longitude']))>.002
    import re
    aa,bb=key(a.get('address')),key(b.get('address'))
    na,nb=re.findall(r'\b\d+\b',aa),re.findall(r'\b\d+\b',bb)
    same_address=bool(aa and bb and na and nb and na[0]==nb[0] and (aa==bb or aa.startswith(bb+' ') or bb.startswith(aa+' ')))
    branch_conflict=bool(aa and bb and na and nb and na[0]!=nb[0]) or far
    namespace_a=a.get('source_name') or domain(a.get('source_url'))
    namespace_b=b.get('source_name') or domain(b.get('source_url'))
    identifier=bool(a.get('source_id') and a.get('source_id')==b.get('source_id') and namespace_a and namespace_a==namespace_b)
    if branch_conflict:
        return ('possible','Identificador repetido com endereço ou coordenadas divergentes.') if identifier else ('distinct','Filiais ou endereços distintos.')
    if name and identifier:return 'confirmed','Nome e identificador na mesma fonte, sem conflito geográfico.'
    if name and city and (same_address or near):return 'confirmed','Nome, município e estabelecimento coincidem.'
    phone=bool(digits(a.get('phone')) and digits(a.get('phone'))==digits(b.get('phone')))
    whatsapp=bool(digits(a.get('whatsapp')) and digits(a.get('whatsapp'))==digits(b.get('whatsapp')))
    site=bool(domain(a.get('website')) and domain(a.get('website'))==domain(b.get('website')))
    if name and same_address and (phone or whatsapp):return 'confirmed','Nome, endereço numerado e contato coincidem.'
    if identifier or (name and (city or same_address or phone or whatsapp or site or near)):
        return 'possible','Há semelhança, mas faltam evidências para confirmar o estabelecimento.'
    from difflib import SequenceMatcher
    if city and (phone or whatsapp or site or same_address) and SequenceMatcher(None,key(a.get('name')),key(b.get('name'))).ratio()>=.8:
        return 'possible','Nome semelhante e dados compartilhados; revisão necessária.'
    return 'distinct','Sem correspondência suficiente.'

def from_lead(lead):
    fields=['name','category','address','city','country','phone','whatsapp','website','instagram','latitude','longitude']
    return {**{f:getattr(lead,f) for f in fields},'source_name':lead.source,'source_id':lead.source_id or ''}
