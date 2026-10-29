import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
async function login(page:Page,email='e2e@example.test'){
  const r=await page.request.post('/api/auth/login',{data:{email,password:'E2e-only-not-for-production!'}});expect(r.ok()).toBeTruthy();
}
async function choose(page:Page,name:string,option:string){
  await page.getByRole('combobox',{name,exact:true}).selectOption({label:option});
}
async function capture(page:Page,name:string){
  await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();document.querySelectorAll('.intelligence-table').forEach(e=>{e.scrollLeft=0;});window.scrollTo({top:0,behavior:'instant'});});
  await expect.poll(()=>page.evaluate(()=>window.scrollY)).toBe(0);
  await page.screenshot({path:`../artifacts/${name}.png`,fullPage:true});
}
test('canonical funnel, sources, provenance and existing learning without history fan-out',async({page})=>{
  await login(page);const activityRequests:string[]=[];
  page.on('request',r=>{if(/\/leads\/[^/]+\/activities/.test(r.url()))activityRequests.push(r.url());});
  await page.goto('/#intelligence');
  await expect(page.locator('[data-metric=contacts] strong')).toHaveText('1');
  await expect(page.locator('[data-metric=replies] strong')).toHaveText('1');
  await expect(page.locator('[data-metric=incorporated] strong')).toHaveText('1');
  await expect(page.getByText('2 empresas na origem selecionada',{exact:false})).toBeVisible();
  await choose(page,'Período','Histórico disponível');
  await expect(page.locator('[data-metric=incorporated] strong')).toHaveText('2');
  await choose(page,'Origem','Absorção');
  await expect(page.locator('[data-metric=incorporated] strong')).toHaveText('1');
  await choose(page,'Origem','Todas as origens');
  await expect(page.locator('[data-metric=incorporated] strong')).toHaveText('2');
  await capture(page,'operations-desktop');
  await page.getByRole('button',{name:'Qualidade comercial',exact:true}).click();
  await expect(page.locator('[data-metric=contacts_accepted] strong')).toHaveText('1');
  await expect(page.locator('[data-metric=contacts_declared] strong')).toHaveText('0');
  await expect(page.locator('[data-metric=delivered] strong')).toHaveText('0');
  await expect(page.getByText('Amostra pequena',{exact:true}).first()).toBeVisible();
  await page.getByText('Comportamento de negociações encerradas',{exact:true}).click();
  await expect(page.getByText('Ainda não há desfechos datados neste período.',{exact:false})).toBeVisible();
  await expect(page.getByText('Casos revisados e qualidade da seleção',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Eficiência',exact:true}).click();
  await expect(page.locator('[data-metric=monetary_cost] strong')).toHaveText('Não disponível');
  await capture(page,'operations-efficiency-desktop');
  expect(activityRequests).toEqual([]);
  expect((await new AxeBuilder({page}).include('.operational-intelligence').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
});

test('empty account has usable funnel and unavailable rates',async({page})=>{
  await login(page,'empty@example.test');await page.goto('/#intelligence');
  await expect(page.getByText('Nenhuma empresa incorporada nesta origem.',{exact:false})).toBeVisible();
  await expect(page.locator('[data-metric=contacts] strong')).toHaveText('0');
  await expect(page.getByText('Sem base',{exact:true})).toHaveCount(5);
  await page.getByRole('button',{name:'Qualidade comercial',exact:true}).click();
  await expect(page.getByText('Nenhuma pendência mensurável nesta consulta.',{exact:true})).toBeVisible();
  await expect(page.getByText('Sem amostra nesta dimensão e período.',{exact:true})).toBeVisible();
});

test('mobile loading, failure, retry, filters and keyboard-scrollable tables',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});await login(page);
  await page.route('**/api/insights/operations?**',route=>route.abort(),{times:1});
  await page.goto('/#intelligence');await expect(page.getByRole('alert').filter({hasText:'Não foi possível carregar os indicadores'})).toBeVisible();
  await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();
  await expect(page.locator('[data-metric=contacts] strong')).toHaveText('1');
  await choose(page,'Período','Últimos 7 dias');await expect(page.locator('[data-metric=contacts] strong')).toHaveText('1');
  await page.getByRole('region',{name:'Etapas observadas',exact:true}).focus();await page.keyboard.press('ArrowRight');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).include('.operational-intelligence').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await capture(page,'operations-390');await page.setViewportSize({width:320,height:800});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await capture(page,'operations-320');
});
