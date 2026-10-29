"""Fictional, explicitly labeled data. Never silently loaded in production."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Lead, Sale, Payment, Expense, Site
from .schemas import LeadInput

EXAMPLES = [
    ('Studio Aurora','Salão',-8.056,-34.897,312,4.8,'none'),
    ('Café do Pátio','Cafeteria',-8.063,-34.883,186,4.7,'none'),
    ('Barbearia Alameda','Barbearia',-8.049,-34.901,224,4.9,'poor'),
    ('Clínica Horizonte','Clínica',-8.041,-34.889,158,4.8,'none'),
    ('Oficina Norte','Oficina',-8.029,-34.909,78,4.4,'none'),
    ('Casa Botânica','Restaurante',-8.071,-34.9,420,4.8,'poor'),
    ('Movimento Pilates','Academia',-8.048,-34.918,43,4.9,'none'),
    ('Odonto Clara','Dentista',-8.075,-34.909,201,4.7,'none'),
    ('Ateliê Forma','Arquitetura',-8.035,-34.897,32,4.6,'unknown'),
    ('Vila do Pão','Padaria',-8.057,-34.912,267,4.5,'good'),
    ('Estúdio Oliva','Design',-8.087,-34.89,57,4.8,'good'),
    ('Mercado Raiz','Mercado',-8.09,-34.913,129,4.5,'poor'),
    ('Pet Jardim','Pet shop',-8.064,-34.928,92,4.7,'none'),
    ('Espaço Serena','Clínica',-8.02,-34.919,103,4.9,'good'),
    ('Casa da Esquina','Restaurante',-8.031,-34.882,383,4.6,'good'),
    ('Bossa Imóveis','Imobiliária',-8.078,-34.922,112,4.6,'good'),
]

def demo_leads():
    return [LeadInput(name=n,category=c,city='Recife',latitude=lat,longitude=lon,reviews=reviews,rating=rating,website_status=site,website='https://example.com' if site in ('good','poor') else '',instagram='https://www.instagram.com/' if i%3 else '',instagram_active=i%3!=0,potential_cents=180000+(i%5)*60000,address='Recife, PE · localização ilustrativa',notes='Estabelecimento fictício para explorar o ScoutLIQ. Não contatar.') for i,(n,c,lat,lon,reviews,rating,site) in enumerate(EXAMPLES)]

def seed_demo(db, user):
    if db.scalar(select(Lead.id).where(Lead.user_id==user.id,Lead.demo==True).limit(1)):
        return False
    today = datetime.now(ZoneInfo(user.timezone)).date()
    for i,item in enumerate(demo_leads()):
        lead = Lead(**item.model_dump(),user_id=user.id,demo=True,source='demo',in_pipeline=i>=2,stage=['discovered','contacted','replied','negotiating'][i%4] if i<10 else 'won')
        db.add(lead)
        db.flush()
        if i>=10:
            day = today-timedelta(days=[0,2,5,9,16,24][i-10])
            sale = Sale(user_id=user.id,lead_id=lead.id,service='Site institucional',amount_cents=lead.potential_cents,recurring_cents=14900 if i%2 else 0,sold_on=str(day),due_on=str(day+timedelta(days=15)),demo=True,project_status='active' if i%2 else 'progress')
            db.add(sale)
            db.flush()
            if i%2:
                db.add(Site(user_id=user.id,sale_id=sale.id,name=lead.name,url='https://example.com',domain='example.com',domain_owner='Cliente fictício',hosting='Hospedagem de exemplo',plan='Hospedagem + suporte',maintenance='Hospedagem, domínio, suporte e pequenas alterações. Novas páginas são serviços extras.',monthly_revenue_cents=14900,monthly_cost_cents=2900,annual_domain_cost_cents=4000,status='active',ssl_status='valid',renewal_on=str(today+timedelta(days=20 if i==11 else 180)),ssl_expires_on=str(today+timedelta(days=60)),demo=True))
            db.add(Payment(user_id=user.id,sale_id=sale.id,amount_cents=sale.amount_cents//2,paid_on=str(day),request_id=str(uuid.uuid4())))
    db.add(Expense(user_id=user.id,description='Hospedagem · exemplo',amount_cents=8900,incurred_on=str(today),demo=True,request_id=str(uuid.uuid4())))
    db.commit()
    return True
