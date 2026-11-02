const {chromium}=require('../apps/web/node_modules/@playwright/test');
const assert=require('node:assert/strict');

async function waitCount(page,selector,count){
  await page.waitForFunction(({selector,count})=>document.querySelectorAll(selector).length===count,{selector,count},{timeout:15000});
}

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const base=process.env.WEB_ORIGIN;
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    page.on('dialog',dialog=>dialog.accept());
    await page.goto(base+'/login');
    await page.locator('#account').fill(process.env.PAGINATION_USER);
    await page.locator('#password').fill(process.env.PAGINATION_PASSWORD);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await page.waitForURL('**/profile');

    const list='/posts?board_id='+process.env.PAGINATION_BOARD;
    await page.goto(base+list);
    await waitCount(page,'ul.topic-list > li',20);
    await page.locator('.pagination-meta').filter({hasText:'第 1 / 3 页 · 共 45 条'}).waitFor();
    const firstTitle=await page.locator('ul.topic-list > li .topic-title a').first().innerText();
    assert.equal(await page.getByRole('button',{name:'上一页',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'第 1 页',exact:true}).getAttribute('aria-current'),'page');

    await page.getByRole('button',{name:'第 2 页',exact:true}).click();
    await page.waitForURL(/page=2/);
    await page.locator('.pagination-meta').filter({hasText:'第 2 / 3 页 · 共 45 条'}).waitFor();
    await waitCount(page,'ul.topic-list > li',20);
    const secondTitle=await page.locator('ul.topic-list > li .topic-title a').first().innerText();
    assert.notEqual(secondTitle,firstTitle);

    await page.getByRole('button',{name:'下一页',exact:true}).click();
    await page.waitForURL(/page=3/);
    await waitCount(page,'ul.topic-list > li',5);
    await page.locator('.pagination-meta').filter({hasText:'第 3 / 3 页 · 共 45 条'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'下一页',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'第 3 页',exact:true}).getAttribute('aria-current'),'page');

    await page.getByLabel('跳转到页码').fill('1');
    await page.getByRole('button',{name:'跳转',exact:true}).click();
    await page.waitForURL(/page=1/);
    await page.locator('.pagination-meta').filter({hasText:'第 1 / 3 页 · 共 45 条'}).waitFor();
    await waitCount(page,'ul.topic-list > li',20);
    assert.equal(await page.getByRole('button',{name:'第 1 页',exact:true}).getAttribute('aria-current'),'page');

    await page.getByLabel('跳转到页码').fill('99');
    await page.getByRole('button',{name:'跳转',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'请输入 1～3 的页码'}).waitFor();
    await waitCount(page,'ul.topic-list > li',20);
    assert.match(page.url(),/page=1/);

    await page.setViewportSize({width:390,height:844});
    await page.goto(base+list);
    await waitCount(page,'ul.topic-list > li',20);
    await page.locator('.pagination').waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.equal(await page.getByLabel('跳转到页码').isVisible(),true);
    console.log('PASS browser: fixed 20/20/5 pages, page buttons, jump validation, disabled edges and 390px layout');
  }finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exit(1)});
