import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import path from 'node:path';

const origin=process.env.E2E_ORIGIN||'http://localhost:9160';
async function prepare(page:Page){
  const login=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});
  expect(login.ok()).toBeTruthy();const headers={'X-CSRF-Token':(await login.json()).csrf,Origin:origin};
  const intent=(await(await page.request.post('/api/smart-searches/interpret',{headers,data:{text:'Clínicas odontológicas em Recife, Brasil',target:25}})).json()).intent;
  const saved=await(await page.request.post('/api/radar/saved-searches',{headers,data:{name:'Pesquisa do plano '+Date.now(),query:{location:'Recife',country:'BR',category:'dentista',commercial_intent:intent}}})).json();
  const configured=await page.request.put(`/api/operations/routines/${saved.id}/configuration`,{headers,data:{version:saved.version,enabled:true,config:{objective:'prospect',interval_hours:24,task_limit:20,daily_task_limit:40,operation_limit:100,daily_operation_limit:150,page_limit:3,candidate_limit:100,investigation_limit:0,cooldown_days:7,duration_minutes:60,max_runs:30,research_mode:'web'}}});
  expect(configured.ok()).toBeTruthy();return{saved,headers,intent};
}
function runWorker(){return new Promise<void>((resolve,reject)=>{
  const child=spawn(process.env.E2E_PYTHON||'python',['tests/planning_browser_fixture.py','worker'],{cwd:path.resolve('..'),env:process.env,windowsHide:true,stdio:'pipe'});
  let output='';child.stderr.on('data',d=>output+=d);child.on('error',reject);child.on('exit',code=>code===0?resolve():reject(new Error(output)));
})}
test('explicit plan consent, real worker, pause/resume and audited history',async({page})=>{
  test.setTimeout(90000);
  const {saved,headers}=await prepare(page);
  await page.setViewportSize({width:1440,height:1000});await page.goto('/#automations');
  const panel=page.getByRole('region',{name:'Planejamento de prospecção'});
  await panel.getByRole('button',{name:'Configurar plano'}).click();
  await panel.getByLabel('Meta diária',{exact:true}).fill('25');
  await panel.getByLabel('Investigações por dia',{exact:true}).fill('0');
  await panel.getByLabel('Início da janela',{exact:true}).fill('00:00');
  await panel.getByLabel('Fim da janela',{exact:true}).fill('23:59');
  for(const day of ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'])await panel.getByLabel(day,{exact:true}).check();
  const options=await(await page.request.get('/api/operations/plan/options')).json();
  const place=options.items.find((o:{id:string})=>o.id===saved.id).location;
  await panel.getByRole('group',{name:'Localizações autorizadas'}).getByRole('checkbox',{name:place,exact:true}).check();
  await panel.getByRole('group',{name:'Pesquisas participantes'}).getByRole('checkbox',{name:new RegExp(saved.name)}).check();
  await panel.getByRole('button',{name:'Salvar configuração'}).click();
  await panel.getByRole('button',{name:'Revisar ativação'}).click();
  await expect(panel.getByRole('button',{name:'Confirmar autorização'})).toBeDisabled();
  await expect(panel.getByText('Ativação bloqueada',{exact:true})).toHaveCount(0);
  const audit=await new AxeBuilder({page}).include('.prospecting-plan').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
  await panel.screenshot({path:'../artifacts/planning-desktop.png'});
  await panel.getByRole('checkbox',{name:'Autorizo a execução recorrente destas pesquisas dentro dos limites apresentados.'}).check();
  await panel.getByRole('button',{name:'Confirmar autorização'}).click();
  await expect(panel.getByRole('button',{name:'Pausar plano'})).toBeVisible();
  await page.goto('about:blank');await runWorker();await page.goto('/#automations');
  await expect(panel.getByText('2 / 25',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'Pausar plano'}).click();
  await panel.getByRole('button',{name:'Revisar retomada'}).click();
  await panel.getByRole('checkbox',{name:'Autorizo a execução recorrente destas pesquisas dentro dos limites apresentados.'}).check();
  await panel.getByRole('button',{name:'Confirmar autorização'}).click();
  await panel.getByRole('button',{name:'Solicitar um ciclo'}).click();await runWorker();
  await panel.getByRole('button',{name:'Atualizar plano'}).click();await expect(panel).toContainText('Sem trabalho adicional autorizado');
  await panel.getByText('Histórico e sugestões',{exact:true}).click();
  await expect(panel).toContainText('Pesquisa selecionada por prioridade');
  await panel.getByRole('button',{name:'Consultar sugestões dos últimos 7 dias'}).click();
  await expect(panel).toContainText('Nenhum ajuste aplicado');
  await panel.screenshot({path:'../artifacts/planning-progress-desktop.png'});
  await panel.getByRole('button',{name:'Pausar plano'}).click();
  await panel.getByRole('button',{name:'Desativar plano e liberar recorrências originais'}).click();
  expect((await(await page.request.get('/api/operations/plan')).json()).state).toBe('disabled');
  const deletion=await page.request.delete('/api/radar/saved-searches/'+saved.id,{headers});expect(deletion.status()).toBe(409);
  const routines=await(await page.request.get('/api/operations/routines')).json();
  const row=routines.find((r:{id:string})=>r.id===saved.id);
  expect((await page.request.post(`/api/operations/routines/${saved.id}/control`,{headers,data:{version:row.version,action:'cancel'}})).ok()).toBeTruthy();
});

test('mobile planning form, failure recovery, keyboard and reduced motion',async({page})=>{
  const {saved,headers,intent}=await prepare(page);
  const aux=await(await page.request.post('/api/radar/saved-searches',{headers,data:{name:'Pesquisa removida QA',query:{location:'Recife',country:'BR',category:'dentista',commercial_intent:intent}}})).json();
  const current=await(await page.request.get('/api/operations/plan')).json();
  expect((await page.request.put('/api/operations/plan',{headers,data:{version:current.version,config:{...current.config,members:[...current.config.members,{saved_search_id:aux.id,priority:1}]}}})).ok()).toBeTruthy();
  expect((await page.request.delete('/api/radar/saved-searches/'+aux.id,{headers})).ok()).toBeTruthy();
  await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/#automations');
  const panel=page.getByRole('region',{name:'Planejamento de prospecção'});
  await panel.getByRole('button',{name:'Editar plano'}).click();
  await panel.getByRole('button',{name:'Remover pesquisa não listada'}).click();
  await panel.getByRole('group',{name:'Pesquisas participantes'}).getByRole('checkbox',{checked:true}).uncheck();
  await expect(panel.getByRole('button',{name:'Salvar configuração'})).toBeDisabled();
  for(const width of [390,320]){
    await page.setViewportSize({width,height:900});
    await page.evaluate(()=>{(document.activeElement as HTMLElement|null)?.blur();window.scrollTo({top:0,behavior:'instant'})});
    const size=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));expect(size.scroll).toBeLessThanOrEqual(size.width+1);
    await panel.screenshot({path:`../artifacts/planning-${width}.png`});
  }
  await panel.getByLabel('Meta diária',{exact:true}).focus();await page.keyboard.press('Control+A');await page.keyboard.type('75');await expect(panel.getByLabel('Meta diária',{exact:true})).toHaveValue('75');
  const audit=await new AxeBuilder({page}).include('.prospecting-plan').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(audit.violations).toEqual([]);
  await panel.getByRole('button',{name:'Cancelar edição'}).click();
  await page.route('**/api/operations/plan',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Planejamento indisponível no teste.'})}));
  await panel.getByRole('button',{name:'Atualizar plano'}).click();await expect(panel.getByRole('alert')).toContainText('Planejamento indisponível');
  await page.unroute('**/api/operations/plan');await panel.getByRole('button',{name:'Atualizar plano'}).click();await expect(panel.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('article',{name:saved.name})).toBeVisible();
});
