const {chromium}=require('../apps/web/node_modules/@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const base=process.env.WEB_ORIGIN;
    const buyerContext=await browser.newContext({viewport:{width:1280,height:900}});
    const buyer=await buyerContext.newPage();
    buyer.on('dialog',dialog=>dialog.accept());
    await buyer.goto(base+'/login');
    await buyer.locator('#account').fill(process.env.ADMIN_BROWSER_USER);
    await buyer.locator('#password').fill(process.env.ADMIN_BROWSER_PASSWORD);
    await buyer.getByRole('button',{name:'登录',exact:true}).click();
    await buyer.waitForURL('**/profile');
    await buyer.goto(base+'/posts/'+process.env.ADMIN_BROWSER_POST);
    const commentItem=buyer.locator('li').filter({hasText:'浏览器举报的评论'}).first();
    await commentItem.getByRole('button',{name:'举报评论',exact:true}).click();
    await commentItem.locator('select').selectOption({label:'辱骂或人身攻击'});
    await commentItem.locator('textarea').fill('浏览器举报说明');
    await commentItem.getByRole('button',{name:'提交举报',exact:true}).click();
    await buyer.getByText('举报已提交，处理结果可在“我的举报”查看。',{exact:true}).first().waitFor();

    const adminContext=await browser.newContext({viewport:{width:1280,height:900}});
    const admin=await adminContext.newPage();
    admin.on('dialog',dialog=>dialog.accept());
    await admin.goto(base+'/login');
    await admin.locator('#account').fill(process.env.ADMIN_BROWSER_ADMIN);
    await admin.locator('#password').fill(process.env.ADMIN_BROWSER_ADMIN_PASSWORD);
    await admin.getByRole('button',{name:'登录',exact:true}).click();
    await admin.waitForURL('**/profile');
    await admin.goto(base+'/admin');
    await admin.getByRole('link',{name:'公告管理',exact:true}).first().click();
    await admin.getByRole('button',{name:'新建公告',exact:true}).click();
    const title='浏览器公告'+Date.now();
    await admin.locator('#announcement-title').fill(title);
    await admin.locator('#announcement-body').fill('浏览器公告正文，用于检查草稿、发布与首页展示。');
    await admin.getByRole('button',{name:'保存草稿',exact:true}).click();
    await admin.getByText('公告已保存为草稿或已更新。',{exact:true}).waitFor();
    await admin.getByRole('button',{name:title,exact:true}).click();
    await admin.locator('#announcement-reason').fill('浏览器验收发布');
    await admin.getByRole('button',{name:'发布',exact:true}).click();
    await admin.getByText('公告已发布。',{exact:true}).waitFor();

    await admin.goto(base+'/admin/reports');
    await admin.getByRole('button',{name:/浏览器举报验收帖/}).first().click();
    await admin.locator('#report-resolution').fill('浏览器验收：评论违规');
    await admin.getByRole('button',{name:'成立并隐藏评论',exact:true}).click();
    await admin.getByText('处理结果已保存。',{exact:true}).waitFor();

    const visitorContext=await browser.newContext({viewport:{width:1280,height:900}});
    const visitor=await visitorContext.newPage();
    await visitor.goto(base+'/');
    await visitor.getByText(title,{exact:true}).first().waitFor();
    await visitor.goto(base+'/posts/'+process.env.ADMIN_BROWSER_POST);
    await visitor.getByText('这条评论已隐藏',{exact:true}).waitFor();

    await admin.goto(base+'/admin/boards');
    await admin.getByRole('heading',{name:'板块管理',exact:true}).waitFor();
    await admin.locator('#new-board-name').fill('浏览器板块'+Date.now().toString().slice(-4));
    await admin.getByRole('button',{name:'新建板块',exact:true}).click();
    await admin.getByText('板块已创建。',{exact:true}).waitFor();
    await admin.goto(base+'/admin/subscriptions');
    await admin.getByRole('heading',{name:'提醒任务',exact:true}).waitFor();
    await admin.getByText('只显示脱敏运行信息',{exact:true}).waitFor();
    await admin.goto(base+'/admin/audit-logs');
    await admin.getByRole('heading',{name:'操作记录',exact:true}).waitFor();
    await admin.getByText(/原因：/).first().waitFor();

    await admin.setViewportSize({width:390,height:844});
    await admin.goto(base+'/admin/reports');
    await admin.getByRole('heading',{name:'举报处理',exact:true}).waitFor();
    assert.equal(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    console.log('PASS browser: comment report, admin decision, announcement publish, home visibility and mobile layout');
  }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)});
