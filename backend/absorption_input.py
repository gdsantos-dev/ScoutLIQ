"""Small bounded parsers and loss-aware normalization; no network, eval or file paths."""
import csv
import io
import json
import math
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit
from pydantic import ValidationError

FIELDS=('name','category','address','district','city','state','country','phone','whatsapp','website','instagram',
        'latitude','longitude','source_url','source_id','source_name','notes','contact','rating','reviews','claims')
COUNTRIES=set('AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split())

def text(value):
    if value is None:return ''
    if not isinstance(value,(str,int,float)) or isinstance(value,bool):raise ValueError('Use um valor simples.')
    value=unicodedata.normalize('NFKC',str(value))
    return ' '.join(''.join(ch for ch in value if unicodedata.category(ch) not in ('Cf','Cc') or ch in '\n\t').split())

def key(value):
    value=unicodedata.normalize('NFKD',text(value)).casefold()
    return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in value if not unicodedata.combining(c))).strip()

ALIASES={
 'name':['nome','empresa','nome da empresa','business name','company name','razao social'],
 'category':['categoria','nicho','setor','category'], 'address':['endereco','endereco completo','address'],
 'district':['bairro','district','neighborhood'],'city':['cidade','municipio','city'],
 'state':['estado','uf','state'],'country':['pais','country','country code'],
 'phone':['telefone','fone','phone','telephone'],'whatsapp':['whatsapp','whats app'],
 'website':['site','website','dominio'],'instagram':['instagram','perfil instagram'],
 'latitude':['latitude','lat'],'longitude':['longitude','lon','lng'],
 'source_url':['url da fonte','source url','link da fonte'],'source_id':['id da fonte','source id','identificador externo'],
 'source_name':['fonte','source name'],'notes':['observacoes','notas','notes','evidencias'],
 'contact':['contato','contact'],'rating':['nota','rating'],'reviews':['avaliacoes','reviews']}
HEADERS={key(label):field for field,labels in ALIASES.items() for label in [field,*labels]}

class ParseError(ValueError):pass

def finite_number(value):
    number=float(value)
    if not math.isfinite(number):raise ValueError('Número não finito.')
    return number

def invalid_constant(value):
    raise ValueError('Constante JSON inválida.')

def parse(raw,format='auto',mapping=None,delimiter=None):
    if len(raw.encode('utf-8'))>48000:raise ParseError('Conteúdo acima de 48 KB.')
    raw=raw.lstrip('\ufeff').strip()
    if not raw:raise ParseError('Cole ou selecione os dados.')
    if format=='auto':format='json' if raw.startswith(('[','{')) else 'table' if '\t' in raw else 'csv'
    if format=='json':
        try:parsed=json.loads(raw,parse_float=finite_number,parse_constant=invalid_constant)
        except (ValueError,RecursionError):raise ParseError('O conteúdo não é JSON válido.') from None
        rows=parsed.get('records') if isinstance(parsed,dict) else parsed
        if not isinstance(rows,list) or not 1<=len(rows)<=50:raise ParseError('Envie de 1 a 50 empresas.')
        return {'format':format,'headers':[],'mapping_required':False,'records':rows,'row_errors':{},'sample':[]}
    if delimiter is not None and delimiter not in [',',';','\t','|']:raise ParseError('Delimitador inválido.')
    try:
        delimiter=delimiter or ('\t' if format=='table' else csv.Sniffer().sniff(raw[:8000],delimiters=',;\t|').delimiter)
        reader=csv.reader(io.StringIO(raw,newline=''),delimiter=delimiter,strict=True)
        all_rows=[]
        for row in reader:
            if not any(cell.strip() for cell in row):continue
            if len(all_rows)>=51:raise ParseError('Máximo de 50 registros por lote.')
            if len(row)>32 or any(len(cell)>4000 for cell in row):raise ParseError('Tabela excede o limite de colunas ou tamanho por célula.')
            all_rows.append(row)
    except (csv.Error,ValueError):raise ParseError('Tabela inválida. Confira o delimitador, cabeçalhos e aspas.') from None
    if len(all_rows)<2:raise ParseError('Inclua cabeçalhos e ao menos uma empresa.')
    headers=all_rows[0]; selected={}; output=[]
    for i,label in enumerate(headers):
        choice=(mapping or {}).get(str(i),HEADERS.get(key(label),''))
        if choice not in (*FIELDS,'','ignore'):raise ParseError('Campo de mapeamento inválido.')
        selected[i]=choice
        output.append({'index':i,'label':text(label)[:160],'field':choice})
    if mapping and any(k not in {str(i) for i in range(len(headers))} for k in mapping):raise ParseError('Coluna de mapeamento inexistente.')
    values=[v for v in selected.values() if v not in ('','ignore')]
    required=not all(selected.values()) or len(values)!=len(set(values)) or 'name' not in values
    records=[];errors={}
    if not required:
        for i,row in enumerate(all_rows[1:]):
            record={field:row[col] if col<len(row) else '' for col,field in selected.items() if field!='ignore'}
            if len(row)!=len(headers):errors[str(i)]=['Quantidade de células diferente dos cabeçalhos. Corrija o registro.']
            records.append(record)
    return {'format':format,'delimiter':delimiter,'headers':output,'mapping_required':required,
            'records':records,'row_errors':errors,'sample':all_rows[1:4],
            'originals':[{'mapped':r,'headers':headers,'cells':row} for r,row in zip(records,all_rows[1:])]}

def url(value,field):
    value=text(value)
    if not value:return ''
    if field=='instagram' and re.fullmatch(r'@?[A-Za-z0-9._]{1,30}',value) and (value.startswith('@') or '.' not in value):
        value='https://www.instagram.com/'+value.lstrip('@')+'/'
    elif '://' not in value:value='https://'+value
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,80,443):
        raise ValueError('Use URL HTTP(S) sem credenciais.')
    host=parsed.hostname.lower().encode('idna').decode()
    if any(ch.isspace() for ch in host) or '.' not in host:raise ValueError('Domínio inválido.')
    if field=='instagram' and host.removeprefix('www.')!='instagram.com':raise ValueError('Informe um perfil Instagram.')
    return urlunsplit((parsed.scheme,host,parsed.path,parsed.query,''))

def normalize(original):
    from .absorption import ResearchRecord
    issues=[];data={}
    if not isinstance(original,dict):return {'name':''},['O registro precisa ser um objeto com campos.']
    for field,value in original.items():
        if field not in FIELDS:
            issues.append('Campo não reconhecido: '+str(field)[:60]);continue
        try:
            if field=='claims':data[field]=value;continue
            value=text(value)
            if field in ('latitude','longitude','rating','reviews'):
                if not value:data[field]=None;continue
                if not re.fullmatch(r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d{1,3})?',value):raise ValueError('Número inválido.')
                number=float(value.replace(',','.'))
                if not math.isfinite(number):raise ValueError('Número não finito.')
                data[field]=int(number) if field=='reviews' and number.is_integer() else number;continue
            if field=='country':
                value={'brasil':'BR','brazil':'BR','portugal':'PT','estados unidos':'US','united states':'US','espanha':'ES','spain':'ES','argentina':'AR','reino unido':'GB','united kingdom':'GB'}.get(key(value),value.upper())
                if value and value not in COUNTRIES:raise ValueError('País não reconhecido; use o código de duas letras.')
            if field in ('website','instagram','source_url'):value=url(value,field)
            if field in ('phone','whatsapp') and value:
                if not re.fullmatch(r'[+()\d .-]+',value):raise ValueError('Formato de telefone não reconhecido; preserve o complemento nas observações.')
                value=re.sub(r'[^0-9]','',value)
                if not 8<=len(value)<=15:raise ValueError('Telefone deve ter de 8 a 15 dígitos, sem inventar DDI.')
            if field=='category':
                value={'dentista':'Odontologia','dentistry':'Odontologia','coffee shop':'Cafeteria','barber shop':'Barbearia','gym':'Academia'}.get(key(value),value)
            data[field]=value
        except (ValueError,TypeError,OverflowError):
            data[field]=None if field in ('latitude','longitude','rating','reviews') else ''
            issues.append(field+': formato inválido; confira o valor original.')
    data.setdefault('name','');data.setdefault('country','')
    try:valid=ResearchRecord.model_validate(data);data=valid.model_dump()
    except ValidationError as exc:
        for e in exc.errors():issues.append(str(e['loc'][0] if e['loc'] else 'coordinates')+': valor inválido; corrija o registro.')
    return data,list(dict.fromkeys(issues))
