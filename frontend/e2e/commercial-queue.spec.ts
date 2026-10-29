import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const origin=process.env.E2E_ORIGIN||'http://localhost:8700';
async function login(page:Page){
 const response=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});
 expect(response.ok()).toBeTruthy();return {'X-CSRF-Token':(await response.json()).csrf,Origin:origin};
}
async function create(page:Page,headers:Record<string,string>,name:string,contact:string){
 const response=await page.request.post('/api/leads',{headers,data:{name,category:'Cafeteria',city:'Recife',country:'BR',latitude:-8.05,longitude:-34.9,website_status:'unknown',phone:'5581999999999',contact}});
 expect(response.status()).toBe(201);return response.json();
}
async function openQueue(page:Page){
 await page.goto('/#radar');await page.getByRole('button',{name:'Fila comercial',exact:true}).click();
 await expect(page.getByRole('region',{name:'Fila comercial'})).toBeVisible();
}
test('desktop partial drafting, preview confirmation and canonical draft review',async({page})=>{
 const headers=await login(page);const name='Café Operação '+Date.now();
 const lead=await create(page,headers,name,'contato@example.org');
 await create(page,headers,'Sem Destinatário '+Date.now(),'');
 await openQueue(page);
 await page.getByRole('button',{name:'Selecionar página',exact:true}).click();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('prepare');
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'Prévia da operação comercial'});
 await expect(modal).toContainText('1 elegíveis de 2');
 await expect(modal).toContainText('Destinatário ausente');
 await expect(modal.getByRole('button',{name:'Confirmar operação',exact:true})).toBeDisabled();
 await modal.getByLabel('Confirmo os efeitos apresentados para as empresas elegíveis.').check();
 await modal.getByRole('button',{name:'Confirmar operação',exact:true}).click();
 await expect(modal).toContainText('Resultado da operação');
 await modal.getByRole('button',{name:'Revisar rascunho de '+name,exact:true}).click();
 const editor=page.getByRole('dialog',{name:'Revisão — '+name});
 await expect(editor).toBeVisible();
 await expect(editor.getByRole('textbox',{name:'Mensagem',exact:true})).toBeVisible();
 await editor.getByRole('textbox',{name:'Mensagem',exact:true}).fill('Olá, equipe. Rascunho revisado de teste, sem envio externo.');
 await expect(editor.getByRole('button',{name:'Aprovar conteúdo',exact:true})).toBeDisabled();
 await editor.getByRole('button',{name:'Salvar alterações',exact:true}).click();
 await expect(editor.getByRole('button',{name:'Aprovar conteúdo',exact:true})).toBeEnabled();
 const workflow=await page.request.get(`/api/leads/${lead.id}/workflow`).then(r=>r.json());
 expect(workflow.drafts).toHaveLength(1);expect(workflow.drafts[0].status).toBe('draft');
 await page.screenshot({path:'../artifacts/commercial-draft-desktop.png',fullPage:true});
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.screenshot({path:'../artifacts/commercial-queue-desktop.png',fullPage:true});
});

test('mobile selection survives filtering and reload; triage can be reopened',async({page})=>{
 await page.setViewportSize({width:390,height:844});const headers=await login(page);
 const first='Triagem A '+Date.now(),second='Triagem B '+Date.now();
 await create(page,headers,first,'');await create(page,headers,second,'');await openQueue(page);
 await page.getByRole('checkbox',{name:'Selecionar '+first,exact:true}).check();
 await page.getByLabel('Empresa, cidade ou setor',{exact:true}).fill(second);
 await page.getByRole('checkbox',{name:'Selecionar '+second,exact:true}).check();
 await page.reload();await expect(page.getByText('2/50 selecionadas',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('deferred');
 await page.getByLabel('Motivo da decisão',{exact:true}).fill('Retomar revisão após confirmação do contato.');
 await page.getByRole('button',{name:'Revisar operação',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'Prévia da operação comercial'});await expect(modal).toContainText('2 elegíveis de 2');
 await modal.getByLabel('Confirmo os efeitos apresentados para as empresas elegíveis.').check();
 await modal.getByRole('button',{name:'Confirmar operação',exact:true}).click();
 await expect(modal).toContainText('Resultado da operação');await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('combobox',{name:'Revisão',exact:true}).selectOption('deferred');
 await expect(page.getByRole('checkbox',{name:'Selecionar '+first,exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:'Selecionar '+first,exact:true}).check();
 await page.getByRole('combobox',{name:'Ação em lote',exact:true}).selectOption('reopen');await page.getByRole('button',{name:'Revisar operação',exact:true}).click();
 await modal.getByLabel('Confirmo os efeitos apresentados para as empresas elegíveis.').check();await modal.getByRole('button',{name:'Confirmar operação',exact:true}).click();
 await expect(modal).toContainText('Resultado da operação');await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('combobox',{name:'Revisão',exact:true}).selectOption('main');await expect(page.getByRole('checkbox',{name:'Selecionar '+first,exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect((await new AxeBuilder({page}).include('.commercial-queue').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:'../artifacts/commercial-queue-390.png',fullPage:true});
 await page.setViewportSize({width:320,height:800});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'../artifacts/commercial-queue-320.png',fullPage:true});
});
