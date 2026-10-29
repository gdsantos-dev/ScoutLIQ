import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { inputDate } from '../src/types';

const origin = process.env.E2E_ORIGIN || 'http://localhost:8015';
async function choose(page: Page, name: string, option: string | RegExp) {
  await page.getByRole('combobox', {name, exact:true}).click();
  await page.getByRole('option',{name:option,exact:typeof option === 'string'}).click();
}

test('human review, preview import, frozen evaluation, approved calibration and rollback in existing views', async ({ page }) => {
  test.setTimeout(180000);
  const login = await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});
  expect(login.ok()).toBeTruthy();
  const headers = {'X-CSRF-Token':(await login.json()).csrf,Origin:origin};
  const stamp = Date.now();
  const dev = `Desenvolvimento ${stamp}`, validation = `Validação ${stamp}`;
  const leads = [];
  for (const name of [dev,validation]) {
    const response = await page.request.post('/api/leads',{headers,data:{name,category:'Cafeteria',city:'Recife',country:'BR',address:`Rua ${name}`,
      latitude:-8.05,longitude:-34.9,website_status:'none',phone:'5581999999999',instagram:'https://instagram.com/example',instagram_active:true,rating:4.8,reviews:312}});
    expect(response.status()).toBe(201);
    const lead = await response.json(); leads.push(lead);
    expect((await page.request.patch(`/api/leads/${lead.id}/stage`,{headers,data:{version:lead.version,stage:'discovered'}})).ok()).toBeTruthy();
  }
  const initial = await page.request.get(`/api/leads/${leads[0].id}/workflow`).then(r => r.json());
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/#pipeline');
  await page.getByText(dev,{exact:true}).first().click();
  await page.getByRole('tab',{name:'Operação',exact:true}).click();
  await page.getByRole('button',{name:'Revisão humana',exact:true}).click();
  await page.getByText('Revisão comercial supervisionada',{exact:true}).click();
  await page.getByLabel('Conjunto de casos',{exact:true}).fill(dev);
  await page.getByLabel('Revisor',{exact:true}).fill('Operador QA controlado');
  await choose(page,'Avaliação humana','Inadequada');
  await page.getByLabel('Justificativa comercial',{exact:true}).fill('Exemplo controlado de divergência para testar a revisão humana.');
  await page.getByLabel('Observação revisada',{exact:true}).fill('O operador revisou a adequação do serviço neste caso controlado.');
  await page.getByLabel('Referência da evidência',{exact:true}).fill('Caderno de QA, sem dados comerciais reais.');
  await page.getByRole('button',{name:'Revisar antes de salvar',exact:true}).click();
  await expect(page.getByRole('region',{name:'Prévia da revisão'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Confirmar revisão',exact:true})).toBeDisabled();
  expect((await page.request.get(`/api/learning/cases?lead_id=${leads[0].id}`).then(r => r.json())).cases).toHaveLength(0);
  await page.getByLabel('Confirmo que as classificações e justificativas foram revisadas por uma pessoa.').check();
  await page.getByRole('button',{name:'Confirmar revisão',exact:true}).click();
  await expect(page.getByText('Revisão registrada. Score preservado.',{exact:true})).toBeVisible();
  expect((await page.request.get(`/api/leads/${leads[0].id}/workflow`).then(r => r.json())).insight.priority).toBe(initial.insight.priority);
  await page.keyboard.press('Escape');
  await page.goto('/#intelligence');
  await page.getByRole('button',{name:'Qualidade comercial',exact:true}).click();
  await page.getByText('Casos revisados e qualidade da seleção',{exact:true}).click();
  await page.getByText('Importar casos em JSON',{exact:true}).click();
  const imported = [{source:'orliq_manual',external_id:`validation-${stamp}`,lead_id:leads[1].id,dataset:validation,split:'validation',
    reviewed_on:inputDate(),reviewer:'Operador QA controlado',label_origin:'human',classification:'unsuitable',
    justification:'Exemplo controlado de divergência com revisão independente declarada.',
    evidence:[{statement:'Avaliação manual do serviço neste caso controlado.',reference:'Caderno QA, validação separada.'}]}];
  await page.getByLabel('JSON dos casos',{exact:true}).fill(JSON.stringify(imported));
  await page.getByRole('button',{name:'Gerar prévia da importação',exact:true}).click();
  await page.getByLabel('Confirmo que as classificações e justificativas foram revisadas por uma pessoa.').check();
  await page.getByRole('button',{name:'Confirmar revisão',exact:true}).click();
  await expect(page.getByText('Importação confirmada.',{exact:true})).toBeVisible();
  await page.getByText('Importar casos em JSON',{exact:true}).click();
  for (const [dataset,split] of [[dev,'Desenvolvimento'],[validation,'Validação']]) {
    await page.getByLabel('Conjunto para avaliação',{exact:true}).fill(dataset);
    await choose(page,'Divisão para avaliação',split);
    await page.getByRole('button',{name:'Registrar avaliação da seleção',exact:true}).click();
    await expect(page.getByRole('region',{name:'Avaliação de oportunidades'})).toContainText(dataset);
    await expect(page.getByText('Amostra insuficiente para concluir qualidade comercial. Valores descritivos.',{exact:true})).toBeVisible();
  }
  await page.getByText('Comparar e revisar critérios do Score',{exact:true}).click();
  await choose(page,'Amostra de desenvolvimento',new RegExp(dev));
  await choose(page,'Amostra de validação',new RegExp(validation));
  await page.getByLabel('Problema e hipótese',{exact:true}).fill('Hipótese de QA para reduzir falsos positivos; não é validação comercial real.');
  await page.getByRole('button',{name:'Comparar nos mesmos casos',exact:true}).click();
  const comparison = page.getByRole('region',{name:'Comparação de critérios'});
  await expect(comparison).toContainText('FP: 1 → 0');
  await expect(page.getByRole('button',{name:'Aplicar critérios aprovados',exact:true})).toBeDisabled();
  await page.getByLabel('Revisei amostras, limitações e possíveis regressões.').check();
  await page.getByLabel('Autorizo alterar os critérios do Score nesta conta.').check();
  await page.getByRole('button',{name:'Aplicar critérios aprovados',exact:true}).click();
  await expect(page.getByText('Critérios aplicados. Scores anteriores preservados no histórico.',{exact:true})).toBeVisible();
  await page.getByText('Histórico e reversão',{exact:true}).click();
  await page.getByLabel('Motivo da reversão',{exact:true}).fill('Retorno ao critério padrão após experimento controlado de QA.');
  await page.getByLabel('Autorizo restaurar os critérios anteriores nesta conta.').check();
  await page.getByRole('button',{name:'Reverter alteração vigente',exact:true}).click();
  await expect(page.getByText('Configuração anterior restaurada. Histórico preservado.',{exact:true})).toBeVisible();
  expect((await page.request.get('/api/learning/calibrations/configuration').then(r => r.json())).engine_version).toBe('3.0');
  await page.getByText('Histórico e reversão',{exact:true}).click();
  for (const width of [320,390,768,1440]) {
    await page.setViewportSize({width,height:900});
    const size = await page.locator('.learning-section').evaluate(e => ({scroll:e.scrollWidth,width:e.clientWidth}));
    expect(size.scroll).toBeLessThanOrEqual(size.width+1);
    if (width===390) await page.screenshot({path:'../artifacts/learning-mobile.png',fullPage:true});
  }
  expect((await new AxeBuilder({page}).include('.learning-section').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({path:'../artifacts/learning-desktop.png',fullPage:true});
  await page.reload();
  await page.getByRole('button',{name:'Qualidade comercial',exact:true}).click();
  await page.getByText('Casos revisados e qualidade da seleção',{exact:true}).click();
  await page.getByText(/Consultar e corrigir casos/).click();
  await expect(page.getByRole('button',{name:new RegExp(validation+' · Inadequada')})).toBeVisible();
});

test('invalid imported records stay reviewable and cannot commit; HTML remains text', async ({page}) => {
  const login=await page.request.post('/api/auth/login',{data:{email:'e2e@example.test',password:'E2e-only-not-for-production!'}});
  expect(login.ok()).toBeTruthy();
  await page.goto('/#intelligence');
  await page.getByRole('button',{name:'Qualidade comercial',exact:true}).click();
  await page.getByText('Casos revisados e qualidade da seleção',{exact:true}).click();
  await page.getByText('Importar casos em JSON',{exact:true}).click();
  await page.getByLabel('JSON dos casos',{exact:true}).fill(JSON.stringify([{external_id:'bad',label_origin:'ai',company:{name:'<script>window.pwned=true</script>'}}]));
  await page.getByRole('button',{name:'Gerar prévia da importação',exact:true}).click();
  await expect(page.getByRole('region',{name:'Prévia da revisão'})).toContainText('Registro 1 · Corrigir');
  await page.getByLabel('Confirmo que as classificações e justificativas foram revisadas por uma pessoa.').check();
  await expect(page.getByRole('button',{name:'Confirmar revisão',exact:true})).toBeDisabled();
  await expect(page.locator('.learning-section script')).toHaveCount(0);
});
