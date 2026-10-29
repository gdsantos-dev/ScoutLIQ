import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

test('review contact, authorize persistent queue, worker acceptance and reply in existing CRM',async({page})=>{
  test.setTimeout(180000);
  const origin=process.env.E2E_ORIGIN||'http://localhost:8016';
  const login=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});
  expect(login.ok()).toBeTruthy();const headers={'X-CSRF-Token':(await login.json()).csrf,Origin:origin};
  const name='Outreach QA '+Date.now();
  const recipient=`recipient-${Date.now()}@example.test`;
  const created=await page.request.post('/api/leads',{headers,data:{name,category:'Cafeteria',city:'Recife',country:'BR',address:'Rua QA '+Date.now(),latitude:-8.05,longitude:-34.9,website_status:'none'}});
  expect(created.status()).toBe(201);const lead=await created.json();const base=`/api/leads/${lead.id}`;
  await page.request.patch(base+'/stage',{headers,data:{version:lead.version,stage:'discovered'}});
  const draftResponse=await page.request.post(base+'/outreach/drafts',{headers,data:{request_id:crypto.randomUUID(),channel:'email',recipient,strategy:'initial'}});
  expect(draftResponse.status()).toBe(201);
  expect((await page.request.put(base+'/recipient-policy',{headers,data:{channel:'email',recipient,basis:'explicit_permission',reference:'Documento de permissão controlada QA.',reason:'Permissão recebida em teste controlado.',market:'BR'}})).ok()).toBeTruthy();
  const d=(await page.request.get(base+'/workflow').then(r=>r.json())).drafts[0];
  expect((await page.request.post(base+`/outreach/drafts/${d.id}/approve`,{headers,data:{version:d.version}})).ok()).toBeTruthy();
  await page.emulateMedia({reducedMotion:'reduce'});
  const account=(await page.request.get('/api/communication/accounts').then(r=>r.json())).accounts[0];
  expect((await page.request.post(`/api/communication/accounts/${account.id}/sync`,{headers,data:{version:account.version,enabled:false}})).ok()).toBeTruthy();
  await page.goto('/#integrations');
  await expect(page.getByRole('region',{name:'Conexão Gmail'})).toContainText('sender@example.test');
  await page.getByLabel('Acompanhar respostas das conversas autorizadas').check();
  await expect(page.getByLabel('Acompanhar respostas das conversas autorizadas')).toBeChecked();
  await expect(page.getByLabel('Acompanhar respostas das conversas autorizadas')).toBeEnabled();
  await page.goto('/#pipeline');await page.getByText(name,{exact:true}).first().click();
  await page.getByRole('tab',{name:'Operação',exact:true}).click();
  await page.getByText('Envio e acompanhamento',{exact:true}).click();
  await page.getByText('Autorizar execução',{exact:true}).click();
  const section=page.getByLabel('Execução da comunicação',{exact:true});
  await expect(section.getByRole('button',{name:'Autorizar e colocar na fila'})).toBeDisabled();
  await section.getByText('Revisar condição de contato',{exact:true}).click();
  for(const field of ['Origem do contato','Evidência da permissão ou solicitação','Referência da revisão de jurisdição','Referência das regras do canal']){
    await section.getByLabel(field,{exact:true}).fill('Evidência controlada de QA; nenhuma homologação externa.');
  }
  for(const label of ['Verifiquei a evidência da permissão ou solicitação.','Revisei as condições aplicáveis à jurisdição.','Revisei as regras do provedor.','O destinatário pode solicitar remoção e será suprimido.']){
    await section.getByLabel(label,{exact:true}).check();
  }
  await section.getByRole('button',{name:'Registrar verificação do contato'}).click();
  await expect(section.getByRole('status')).toContainText('Nenhum envio autorizado');
  await section.getByRole('combobox',{name:'Conta remetente'}).click();
  await page.getByRole('option',{name:'sender@example.test',exact:true}).click();
  await section.getByLabel('Referência da identidade remetente',{exact:true}).fill('Identidade controlada em teste, não conta real.');
  await section.getByLabel('Revisão SPF, DKIM e DMARC',{exact:true}).fill('Resultado sintético QA, sem verificação externa de DNS.');
  await section.getByLabel('Confirmo que a conta identifica legitimamente o remetente.').check();
  await section.getByLabel('Revisei a identificação e a opção de remoção no texto aprovado.').check();
  await section.getByLabel(/Autorizo este envio externo/).check();
  expect((await section.getByLabel(/Autorizo este envio externo/).boundingBox())?.width).toBeGreaterThanOrEqual(16);
  await section.getByRole('button',{name:'Autorizar e colocar na fila'}).click();
  await expect(section.getByText('Na fila',{exact:true})).toBeVisible();
  const outbox=await page.request.get(`/api/communication/outbox?lead_id=${lead.id}`).then(r=>r.json());expect(outbox.messages).toHaveLength(1);
  const root=path.resolve('..');
  const result=execFileSync(process.env.E2E_PYTHON||path.resolve(root,'../../../.venv/Scripts/python.exe'),['tests/communication_browser_fixture.py','worker'],{cwd:root,env:{...process.env,E2E_PORT:process.env.E2E_PORT || new URL(origin).port},timeout:90000,encoding:'utf8'});
  expect(result).not.toContain('Traceback');
  await section.getByRole('button',{name:'Atualizar fila'}).click();
  await expect(section.getByText('Aceita pelo provedor',{exact:true})).toBeVisible();
  await expect(section.getByText('Entrega e leitura não confirmadas.',{exact:true})).toBeVisible();
  const activities=await page.request.get(base+'/activities').then(r=>r.json());
  expect(activities.some((a:{metadata:{event?:string;classification?:string}})=>a.metadata.event==='outreach_reply'&&a.metadata.classification==='interest')).toBeTruthy();
  await section.getByRole('button',{name:'Consultar autorização e histórico'}).click();
  await expect(section.getByRole('region',{name:'Autorização e histórico da mensagem'})).toContainText('sender@example.test');
  for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  }
  const axe=await new AxeBuilder({page}).include('[aria-label="Execução da comunicação"]').analyze();
  expect(axe.violations).toEqual([]);
  await page.screenshot({path:'../artifacts/communication-desktop.png'});
  await page.setViewportSize({width:390,height:844});await section.scrollIntoViewIfNeeded();
  await page.screenshot({path:'../artifacts/communication-mobile.png'});
});
