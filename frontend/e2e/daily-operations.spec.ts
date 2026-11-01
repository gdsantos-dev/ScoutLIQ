import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import path from 'node:path';
const origin=process.env.E2E_ORIGIN||'http://localhost:9300';
async function login(page:Page){const r=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});expect(r.ok()).toBeTruthy();return {'X-CSRF-Token':(await r.json()).csrf,Origin:origin};}
async function openDaily(page:Page){await page.goto('/#radar');await page.getByRole('button',{name:'Fila comercial',exact:true}).click();await page.getByRole('button',{name:'Operação do dia',exact:true}).click();await expect(page.getByRole('region',{name:'Resumo da operação diária'})).toBeVisible();}
function worker(mode='drain'){return new Promise<void>((resolve,reject)=>{const child=spawn(process.env.E2E_PYTHON||'python',['tests/daily_browser_fixture.py',mode],{cwd:path.resolve('..'),env:process.env,windowsHide:true,stdio:'pipe'});let output='';child.stderr.on('data',d=>output+=d);child.on('error',reject);child.on('exit',code=>code===0?resolve():reject(new Error(output)));});}
async function confirm(page:Page){const modal=page.getByRole('dialog',{name:'Prévia da operação comercial'});await expect(modal.getByRole('button',{name:'Confirmar operação',exact:true})).toBeDisabled();await modal.getByLabel('Confirmo os efeitos apresentados para as empresas elegíveis.').check();await modal.getByRole('button',{name:'Confirmar operação',exact:true}).click();await expect(modal).toContainText('Resultado da operação');await page.keyboard.press('Escape');}

test('plan discovery investigation daily review and preparation share canonical contracts',async({page})=>{
 test.setTimeout(240000);const headers=await login(page);
 expect((await page.request.put('/api/investigation/preferences',{headers,data:{search:true,absorption:false,execution_limit:20,daily_limit:40,operation_limit:100,daily_operation_limit:150,freshness_days:30,allow_deep:false}})).ok()).toBeTruthy();
 const intent=(await(await page.request.post('/api/smart-searches/interpret',{headers,data:{text:'Clínicas odontológicas em Recife, Brasil',target:25}})).json()).intent;
 const saved=await(await page.request.post('/api/radar/saved-searches',{headers,data:{name:'Operação diária QA',query:{location:'Recife',country:'BR',category:'dentista',commercial_intent:intent}}})).json();
 expect((await page.request.put(`/api/operations/routines/${saved.id}/configuration`,{headers,data:{version:saved.version,enabled:true,config:{objective:'prospect',interval_hours:24,task_limit:20,daily_task_limit:40,operation_limit:100,daily_operation_limit:150,page_limit:3,candidate_limit:100,investigation_limit:2,cooldown_days:7,duration_minutes:60,max_runs:30,research_mode:'web'}}})).ok()).toBeTruthy();
 const options=await(await page.request.get('/api/operations/plan/options')).json();
 const config={daily_target:2,members:[{saved_search_id:saved.id,priority:1}],locations:[options.items.find((x:{id:string})=>x.id===saved.id).location],weekdays:[0,1,2,3,4,5,6],window_start:'00:00',window_end:'23:59',daily_runs:2,companies_per_search:25,daily_investigations:2,daily_operations:20,cooldown_hours:24};
 const plan=await(await page.request.put('/api/operations/plan',{headers,data:{version:0,config}})).json();
 const approval=await(await page.request.get('/api/operations/plan/preview')).json();
 expect((await page.request.post('/api/operations/plan/control',{headers,data:{version:plan.version,action:'activate',confirm:true,preview_token:approval.token}})).ok()).toBeTruthy();
 await worker('discover');await openDaily(page);
 const summary=page.getByRole('region',{name:'Resumo da operação diária'});
 await expect(summary).toContainText('2 / 2');
 let snapshot=await(await page.request.get('/api/commercial-review/queue?view=daily')).json();expect(snapshot.daily.investigating).toBe(2);expect(snapshot.daily.investigated).toBe(0);
 await page.goto('about:blank');await worker();await openDaily(page);
 snapshot=await(await page.request.get('/api/commercial-review/queue?view=daily')).json();expect(snapshot.daily.plan_incorporated).toBe(2);expect(snapshot.daily.investigated).toBe(2);expect(snapshot.daily.ready).toBe(2);
 const finalPlan=await(await page.request.get('/api/operations/plan')).json();expect(finalPlan.config).toEqual(config);
 await page.getByRole('button',{name:'Filtrar atenção de oportunidades qualificadas: 2',exact:true}).click();await expect(page.getByRole('combobox',{name:'Classificação',exact:true})).toHaveValue('priority');await page.getByRole('combobox',{name:'Classificação',exact:true}).selectOption('');
 await page.getByRole('combobox',{name:'Empresas',exact:true}).selectOption('plan');await expect(page.getByRole('checkbox',{name:/Selecionar Clínica/})).toHaveCount(2);
 await page.getByRole('button',{name:'Selecionar página',exact:true}).click();await page.getByRole('button',{name:'Revisar operação',exact:true}).click();await confirm(page);
 await expect(page.getByText('2/50 selecionadas',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('prepare');await page.getByRole('button',{name:'Revisar operação',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('2 elegíveis de 2');await confirm(page);
 for(const row of snapshot.items){const wf=await(await page.request.get(`/api/leads/${row.id}/workflow`)).json();expect(wf.drafts).toHaveLength(1);expect(wf.drafts[0].status).toBe('draft');}
 await page.getByText('Pesquisas e decisões do plano',{exact:true}).click();await page.getByRole('button',{name:'Ver investigação',exact:true}).click();await expect(page.getByText('Investigação concluída',{exact:true})).toBeVisible();
 await openDaily(page);await page.setViewportSize({width:1440,height:1000});await page.getByRole('combobox',{name:'Empresas',exact:true}).selectOption('all');
 expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.evaluate(()=>{(document.activeElement as HTMLElement|null)?.blur();window.scrollTo(0,0);});await page.screenshot({path:'../artifacts/daily-desktop.png',fullPage:true});
});

test('daily mobile keyboard reduced motion and retry preserve selection',async({page})=>{
 const headers=await login(page);const name='Pendência diária '+Date.now();
 expect((await page.request.post('/api/leads',{headers,data:{name,category:'Cafeteria',city:'Recife',country:'BR',latitude:-8,longitude:-34,website_status:'unknown'}})).ok()).toBeTruthy();
 await page.emulateMedia({reducedMotion:'reduce'});await openDaily(page);await expect(page.getByRole('region',{name:'Resumo da operação diária'})).toContainText('3 / 2');
 await page.getByLabel('Empresa, cidade ou setor',{exact:true}).fill(name);const box=page.getByRole('checkbox',{name:'Selecionar '+name,exact:true});await box.focus();await page.keyboard.press('Space');await expect(box).toBeChecked();
 await page.getByRole('button',{name:'Triagem',exact:true}).click();await expect(page.getByText('1/50 selecionadas',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Operação do dia',exact:true}).click();
 for(const width of [768,390,320]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);await page.evaluate(()=>{(document.activeElement as HTMLElement|null)?.blur();window.scrollTo(0,0);});await page.screenshot({path:`../artifacts/daily-${width}.png`,fullPage:true});}
 await page.route('**/api/commercial-review/queue?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Fila indisponível no teste.'})}));await page.getByRole('button',{name:'Atualizar',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Fila indisponível');
 await page.unroute('**/api/commercial-review/queue?**');await page.getByRole('button',{name:'Atualizar fila',exact:true}).click();await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.getByText('1/50 selecionadas',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('prepare');await page.getByRole('button',{name:'Revisar operação',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('Destinatário ausente');await expect(page.getByRole('button',{name:'Confirmar operação',exact:true})).toBeDisabled();
});
