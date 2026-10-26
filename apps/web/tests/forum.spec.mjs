import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
test.use({trace:'off'});
test.setTimeout(150000);
const enabled=process.env.E2E_FORUM==='1',suffix=process.env.FORUM_SUFFIX||'unused';
const password=process.env.FORUM_PASSWORD||'';
async function login(page,account){await page.goto('/login');await page.getByLabel('账号',{exact:true}).fill(account);await page.getByLabel('密码',{exact:true}).fill(password);await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL(/\/profile$/);}

test('浏览器发帖、通用上传、回复收藏、编辑与移动显示',async({page})=>{
  test.skip(!enabled);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await login(page,process.env.FORUM_ALICE);await page.getByRole('link',{name:'论坛',exact:true}).click();
  await page.getByRole('link',{name:'发布帖子',exact:true}).last().click();
  const title='浏览器校园交流'+suffix;
  await page.getByLabel('板块',{exact:true}).selectOption(process.env.FORUM_BOARD);
  await page.getByLabel('标题',{exact:true}).fill(title);
  await page.getByLabel('正文',{exact:true}).fill('## 浏览器正文\n\n**重要信息**\n\n<script>window.forumInjected=true</script>\n\n[危险链接](javascript:alert(1))\n\n![外部图片](https://invalid.example/tracker.png)');
  await page.getByLabel('上传图片',{exact:true}).setInputFiles(process.env.FORUM_PNG);
  await expect(page.locator('.upload-list li')).toHaveCount(1);
  await expect(page.getByRole('status').filter({hasText:'正在处理文件'})).toHaveCount(0);
  await page.getByLabel('上传 PDF',{exact:true}).setInputFiles(process.env.FORUM_PDF);
  await expect(page.locator('.upload-list li')).toHaveCount(2);
  await expect(page.getByRole('status').filter({hasText:'正在处理文件'})).toHaveCount(0);
  await page.getByRole('button',{name:'预览正文',exact:true}).click();
  await expect(page.getByRole('heading',{name:'浏览器正文',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'发布帖子',exact:true}).click();await expect(page).toHaveURL(/\/posts\/\d+$/);
  await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
  const postPath=new URL(page.url()).pathname;
  await page.reload();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
  expect(await page.evaluate(()=>window.forumInjected)).toBeUndefined();
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);await expect(page.locator('img[src^="https://invalid.example"]')).toHaveCount(0);
  await expect(page.locator('.post-images img')).toBeVisible();await expect(page.locator('.pdf-list a')).toHaveText('fixture.pdf');
  const oldImage=await page.locator('.post-images a').getAttribute('href');
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('.pdf-list a').click()]);expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await page.getByLabel('写回复',{exact:true}).fill('浏览器保存的回复');await page.getByRole('button',{name:'提交回复',exact:true}).click();await expect(page.getByRole('status')).toContainText('回复已保存');
  await page.getByRole('button',{name:'点赞',exact:true}).click();await expect(page.getByRole('button',{name:'取消点赞',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'收藏',exact:true}).click();await expect(page.getByRole('button',{name:'取消收藏',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'我的收藏',exact:true}).click();await expect(page.getByRole('link',{name:title,exact:true})).toBeVisible();
  await page.getByRole('link',{name:title,exact:true}).click();await page.getByRole('link',{name:'编辑帖子',exact:true}).click();
  await page.getByLabel('标题',{exact:true}).fill(title+'已编辑');
  await page.getByRole('group',{name:'图片',exact:true}).getByRole('button',{name:'移除',exact:true}).click();
  await page.getByRole('button',{name:'保存修改',exact:true}).click();await expect(page.getByRole('heading',{name:title+'已编辑',exact:true})).toBeVisible();
  expect((await page.request.get(oldImage)).status()).toBe(404);
  await page.setViewportSize({width:375,height:812});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:path.resolve('../../.local/logs/forum/post-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1280,height:900});await page.goto('/posts?board_id='+process.env.FORUM_BOARD+'&sort=popular');
  await expect(page.getByRole('link',{name:title+'已编辑',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('combobox',{name:'板块',exact:true})).toHaveValue(process.env.FORUM_BOARD);
  await page.screenshot({path:path.resolve('../../.local/logs/forum/forum.png'),fullPage:true});
  expect(postPath).toMatch(/^\/posts\/\d+$/);expect(errors).toEqual([]);
});

test('授权版主可管理本人板块，其他板块和普通用户管理入口受限',async({browser})=>{
  test.skip(!enabled);
  const context=await browser.newContext(),page=await context.newPage();await login(page,process.env.FORUM_MOD);
  await page.goto('/admin/posts/'+process.env.FORUM_POST);await expect(page.getByRole('heading',{name:'管理帖子',exact:true})).toBeVisible();
  await page.getByLabel('操作原因',{exact:true}).fill('浏览器检查隐藏');await page.getByRole('button',{name:'隐藏帖子',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('管理操作已保存');await expect(page.getByRole('button',{name:'恢复帖子',exact:true})).toBeVisible();
  const visitor=await browser.newContext();const guest=await visitor.newPage();await guest.goto('/posts/'+process.env.FORUM_POST);await expect(guest.getByRole('alert').filter({hasText:'内容不存在'})).toContainText('内容不存在');
  await page.getByRole('button',{name:'恢复帖子',exact:true}).click();await expect(page.getByRole('button',{name:'隐藏帖子',exact:true})).toBeVisible();
  await page.goto('/admin/posts/'+process.env.FORUM_OTHER_POST);await expect(page.getByRole('alert').filter({hasText:'没有执行'})).toContainText('没有执行');
  await login(guest,process.env.FORUM_BOB);await guest.goto('/admin/posts');await expect(guest.getByRole('heading',{name:'没有访问权限',exact:true})).toBeVisible();
  await context.close();await visitor.close();
});

test('真实数据库故障时发帖失败保留表单，恢复后可保存',async({page})=>{
  test.skip(!enabled);
  await login(page,process.env.FORUM_ALICE);await page.goto('/posts/new');
  await page.getByLabel('标题',{exact:true}).fill('故障恢复发帖'+suffix);await page.getByLabel('正文',{exact:true}).fill('数据库失败时保留这些内容');
  const root=path.resolve('../..');
  const compose=['compose','--env-file',path.join(root,'deploy/.env'),'-f',path.join(root,'deploy/compose.dev.yaml')];
  let stopped=false;
  try{
    execFileSync('docker',[...compose,'stop','mysql'],{cwd:root,stdio:'pipe',timeout:60000});stopped=true;
    await page.getByRole('button',{name:'发布帖子',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'服务暂时不可用'})).toBeVisible({timeout:25000});
    await expect(page.getByLabel('标题',{exact:true})).toHaveValue('故障恢复发帖'+suffix);await expect(page.getByLabel('正文',{exact:true})).toHaveValue('数据库失败时保留这些内容');expect(new URL(page.url()).pathname).toBe('/posts/new');
    await page.screenshot({path:path.resolve('../../.local/logs/forum/database-failure.png'),fullPage:true});
  }finally{if(stopped)execFileSync('docker',[...compose,'up','-d','--wait','--wait-timeout','120'],{cwd:root,stdio:'pipe',timeout:150000});}
  await expect.poll(async()=>{try{return(await page.request.get('/health/ready')).status();}catch{return 0;}},{timeout:30000}).toBe(200);
  await page.getByRole('button',{name:'发布帖子',exact:true}).click();await expect(page.getByRole('heading',{name:'故障恢复发帖'+suffix,exact:true})).toBeVisible();
});
