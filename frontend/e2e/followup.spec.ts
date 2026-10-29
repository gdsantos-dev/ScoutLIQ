import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const origin=process.env.E2E_ORIGIN||'http://localhost:8900';
const before=new Date(Date.now()-10*86400000).toISOString().slice(0,10);
const after=new Date(Date.now()+10*86400000).toISOString().slice(0,10);
async function login(page:Page){const r=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});expect(r.ok()).toBeTruthy();return {'X-CSRF-Token':(await r.json()).csrf,Origin:origin};}
async function create(page:Page,headers:Record<string,string>,name:string,contact='test@example.org'){
 const r=await page.request.post('/api/leads',{headers,data:{name,contact,category:'Cafeteria',city:'Recife',country:'BR',latitude:-8,longitude:-34,website_status:'unknown'}});expect(r.status()).toBe(201);const lead=await r.json();
 const move=await page.request.patch(`/api/leads/${lead.id}/stage`,{headers,data:{version:lead.version,stage:'discovered'}});expect(move.ok()).toBeTruthy();return move.json();
}
async function open(page:Page){await page.goto('/#pipeline');await page.getByRole('button',{name:'Acompanhamento comercial',exact:true}).click();await expect(page.getByRole('region',{name:'Fila comercial'})).toBeVisible();}
async function confirm(page:Page){const modal=page.getByRole('dialog',{name:'Prévia da operação comercial'});await modal.getByLabel('Confirmo os efeitos apresentados para as empresas elegíveis.').check();await modal.getByRole('button',{name:'Confirmar operação',exact:true}).click();await expect(modal).toContainText('Resultado da operação');return modal;}

test('desktop manual provenance, partial followup and canonical editor without sending',async({page})=>{
 const headers=await login(page),prefix='Acompanhamento '+Date.now();const name=prefix+' Contatado';
 const lead=await create(page,headers,name);await create(page,headers,prefix+' Sem contato','');await open(page);
 await page.getByLabel('Empresa, cidade ou setor',{exact:true}).fill(prefix);
 await page.getByText('Resumo de '+name,{exact:true}).click();
 await page.getByRole('button',{name:'Registrar atividade de '+name,exact:true}).click();
 const manual=page.getByRole('dialog',{name:'Registrar atividade — '+name});
 await manual.getByLabel('Data do ocorrido',{exact:true}).fill(before);await manual.getByLabel('Observações',{exact:true}).fill('E-mail realizado manualmente; declaração de teste.');
 await manual.getByRole('button',{name:'Salvar atividade',exact:true}).click();await expect(manual).toHaveCount(0);
 await expect(page.getByText('Revisar follow-up',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Selecionar página',exact:true}).click();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('followup_prepare');
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();
 const preview=page.getByRole('dialog',{name:'Prévia da operação comercial'});await expect(preview).toContainText('1 elegíveis de 2');
 await preview.getByText('Conferir rascunho para test@example.org',{exact:true}).click();
 await expect(preview).toContainText('Retomo nossa conversa anterior.');
 await page.screenshot({path:'../artifacts/followup-preview-desktop.png',fullPage:true});
 const result=await confirm(page);await result.getByRole('button',{name:'Revisar rascunho de '+name,exact:true}).click();
 const editor=page.getByRole('dialog',{name:'Revisão — '+name});await expect(editor.getByRole('textbox',{name:'Mensagem',exact:true})).toBeVisible();
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 const workflow=await page.request.get(`/api/leads/${lead.id}/workflow`).then(r=>r.json());expect(workflow.drafts).toHaveLength(1);expect(workflow.drafts[0].strategy).toBe('follow_up');
 const outbox=await page.request.get('/api/communication/outbox').then(r=>r.json());expect(outbox.messages).toEqual([]);
 expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo({top:0,behavior:'instant'});});await expect.poll(()=>page.evaluate(()=>window.scrollY)).toBe(0);await page.screenshot({path:'../artifacts/followup-desktop.png',fullPage:true});
});

test('mobile explicit overwrite, pause, reopen and settings persist',async({page})=>{
 await page.setViewportSize({width:390,height:844});const headers=await login(page),name='Ação mobile '+Date.now();const lead=await create(page,headers,name);
 expect((await page.request.patch(`/api/leads/${lead.id}/next-action`,{headers,data:{version:lead.version,next_action:'Compromisso humano',next_action_on:after}})).ok()).toBeTruthy();
 await open(page);await page.getByLabel('Empresa, cidade ou setor',{exact:true}).fill(name);
 await page.getByRole('checkbox',{name:'Selecionar '+name,exact:true}).check();
 await page.getByLabel('Próxima ação',{exact:true}).fill('Revisar condições combinadas');await page.getByLabel('Data da ação',{exact:true}).fill(after);
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();const modal=page.getByRole('dialog',{name:'Prévia da operação comercial'});await expect(modal).toContainText('0 elegíveis de 1');
 await page.keyboard.press('Escape');await expect(modal).toHaveCount(0);
 await page.getByLabel('Permitir substituir ou concluir ações manuais existentes, conforme a prévia.',{exact:true}).check();
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();await expect(modal).toContainText('Compromisso humano');await expect(modal).toContainText('Revisar condições combinadas');
 await confirm(page);await page.keyboard.press('Escape');await expect(modal).toHaveCount(0);
 await expect(page.getByText('Ação agendada',{exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:'Selecionar '+name,exact:true}).check();await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('followup_disable');
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();await confirm(page);await page.keyboard.press('Escape');await expect(modal).toHaveCount(0);
 await expect(page.getByText('Acompanhamento desativado',{exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:'Selecionar '+name,exact:true}).check();await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('followup_enable');
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();await confirm(page);await page.keyboard.press('Escape');await expect(modal).toHaveCount(0);
 await page.getByText('Intervalo de acompanhamento',{exact:true}).click();await page.getByLabel('Dias após contato',{exact:true}).fill('12');await page.getByRole('button',{name:'Salvar intervalo',exact:true}).click();
 await expect.poll(async()=>page.request.get('/api/followup/settings').then(r=>r.json()).then(s=>s.interval_days)).toBe(12);
 await page.reload();await page.getByRole('button',{name:'Acompanhamento comercial',exact:true}).click();await page.getByLabel('Empresa, cidade ou setor',{exact:true}).fill(name);
 await page.getByText('Resumo de '+name,{exact:true}).click();await expect(page.getByText(/Ação registrada: Revisar condições combinadas/)).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo({top:0,behavior:'instant'});});await expect.poll(()=>page.evaluate(()=>window.scrollY)).toBe(0);await page.screenshot({path:'../artifacts/followup-390.png',fullPage:true});await page.setViewportSize({width:320,height:800});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'../artifacts/followup-320.png',fullPage:true});
});
