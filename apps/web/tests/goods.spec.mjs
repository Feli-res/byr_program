import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
test.use({trace:'off'});test.setTimeout(150000);
const enabled=process.env.E2E_GOODS==='1',suffix=process.env.GOODS_SUFFIX||'unused';
async function login(page,account){await page.goto('/login');await page.getByLabel('账号',{exact:true}).fill(account);await page.getByLabel('密码',{exact:true}).fill(process.env.GOODS_PASSWORD||'');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL(/\/profile$/);}
async function upload(page,count=1){await page.getByLabel('上传图片',{exact:true}).setInputFiles(Array(count).fill(process.env.GOODS_PNG));await expect(page.locator('.upload-list li')).toHaveCount(count);await expect(page.getByRole('status').filter({hasText:'正在处理文件'})).toHaveCount(0);}

test('商品发布、整数价格、图片排序编辑和出售状态',async({page})=>{
  test.skip(!enabled);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await login(page,process.env.GOODS_ALICE);await page.getByRole('link',{name:'商品',exact:true}).click();await page.getByRole('link',{name:'发布商品',exact:true}).last().click();
  const title='浏览器闲置平板'+suffix;
  await page.getByLabel('商品标题',{exact:true}).fill(title);await page.getByLabel('商品描述',{exact:true}).fill('浏览器发布的真实描述 <script>window.goodsInjected=true</script>');
  await page.getByLabel('价格（元）',{exact:true}).fill('1.001');await page.getByLabel('交易地点',{exact:true}).fill('图书馆门口');await upload(page,2);
  await page.getByRole('button',{name:'发布商品',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'最多两位小数'})).toBeVisible();expect(new URL(page.url()).pathname).toBe('/goods/new');
  await page.getByLabel('价格（元）',{exact:true}).fill('0.29');await page.getByRole('button',{name:'发布商品',exact:true}).click();await expect(page).toHaveURL(/\/goods\/\d+/);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
  let gid=new URL(page.url()).pathname.split('/').pop();let data=(await(await page.request.get('/api/v1/goods/'+gid)).json()).data;expect(data.price_cents).toBe(29);expect(data.images).toHaveLength(2);
  const oldFirst=data.images[0].url;await page.reload();await expect(page.locator('.goods-detail-price')).toContainText('0.29');expect(await page.evaluate(()=>window.goodsInjected)).toBeUndefined();
  await page.getByRole('link',{name:'编辑商品',exact:true}).click();await page.getByLabel('价格（元）',{exact:true}).fill('30.10');await page.locator('.upload-list li').nth(1).getByRole('button',{name:'上移'}).click();await page.getByRole('button',{name:'保存修改',exact:true}).click();await expect(page.locator('.goods-detail-price')).toContainText('30.10');
  data=(await(await page.request.get('/api/v1/goods/'+gid)).json()).data;expect(data.price_cents).toBe(3010);expect(data.images[1].url).toBe(oldFirst);
  await page.getByRole('link',{name:'编辑商品',exact:true}).click();await page.locator('.upload-list li').nth(1).getByRole('button',{name:'移除',exact:true}).click();await page.getByRole('button',{name:'保存修改',exact:true}).click();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();expect((await page.request.get(oldFirst)).status()).toBe(404);
  for(const [button,label] of [['标记预留','已预留'],['取消预留','在售'],['下架商品','已下架'],['重新上架','在售'],['标记已售','已售']]){await page.getByRole('button',{name:button,exact:true}).click();await expect(page.locator('.panel-heading .tag')).toHaveText(label);}
  await expect(page.getByRole('link',{name:'编辑商品',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'重新上架',exact:true})).toHaveCount(0);
  await page.setViewportSize({width:375,height:812});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:path.resolve('../../.local/logs/goods/detail-mobile.png'),fullPage:true});expect(errors).toEqual([]);
});

test('帖子商品统一搜索、精确筛选、分页与返回时保留条件',async({page})=>{
  test.skip(!enabled);
  await page.goto('/search?q='+encodeURIComponent('检索共同词')+'&page_size=1');await expect(page.locator('.search-results li')).toHaveCount(1);await page.getByRole('button',{name:'下一页',exact:true}).click();
  await expect(page).toHaveURL(/page=2/);await expect(page.locator('.search-results li')).toHaveCount(1);const searchURL=new URL(page.url()).search;
  await page.locator('.search-results .topic-title a').click();await page.getByRole('link',{name:'← 返回列表',exact:true}).click();await expect.poll(()=>new URL(page.url()).search).toBe(searchURL);
  await page.getByLabel('内容类型',{exact:true}).selectOption('goods');await page.getByLabel('类别',{exact:true}).selectOption(process.env.GOODS_CATEGORY);await page.getByLabel('交易校区',{exact:true}).selectOption('shahe');await page.getByLabel('最高价格（元）',{exact:true}).fill('10.00');await page.getByRole('button',{name:'搜索',exact:true}).click();
  await expect(page.locator('.search-results li')).toHaveCount(1);await expect(page.locator('.search-results li')).toContainText('检索共同词商品');await page.reload();await expect(page.getByLabel('最高价格（元）',{exact:true})).toHaveValue('10.00');await expect(page.getByLabel('交易校区',{exact:true})).toHaveValue('shahe');
  const filteredURL=new URL(page.url()).search;await page.locator('.search-results .topic-title a').click();await page.getByRole('link',{name:'← 返回列表',exact:true}).click();await expect.poll(()=>new URL(page.url()).search).toBe(filteredURL);
  await page.setViewportSize({width:375,height:812});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:path.resolve('../../.local/logs/goods/search-mobile.png'),fullPage:true});
  await page.getByLabel('关键词',{exact:true}).fill('不存在的物品'+suffix);await page.getByRole('button',{name:'搜索',exact:true}).click();await expect(page.getByText('没有符合条件的结果，可调整关键词或筛选条件。',{exact:true})).toBeVisible();
});

test('管理员下架立即影响详情、图片和搜索，解除后卖家自行上架',async({browser})=>{
  test.skip(!enabled);
  const manager=await browser.newContext(),owner=await browser.newContext(),visitor=await browser.newContext();const page=await manager.newPage(),seller=await owner.newPage(),guest=await visitor.newPage();
  await login(page,process.env.GOODS_ADMIN);await login(seller,process.env.GOODS_ALICE);const gid=process.env.GOODS_SEED;
  const original=(await(await seller.request.get('/api/v1/goods/'+gid)).json()).data;
  await page.goto('/admin/goods/'+gid);await page.getByLabel('操作原因',{exact:true}).fill('浏览器管理下架检查');await page.getByRole('button',{name:'管理下架',exact:true}).click();await expect(page.getByRole('button',{name:'解除限制',exact:true})).toBeVisible();
  await guest.goto('/goods/'+gid);await expect(guest.getByRole('alert').filter({hasText:'内容不存在'})).toBeVisible();expect((await guest.request.get(original.images[0].url)).status()).toBe(404);
  await seller.goto('/me/goods/'+gid);await expect(seller.getByRole('alert').filter({hasText:'商品受管理限制'})).toBeVisible();await expect(seller.getByRole('button',{name:'重新上架',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'解除限制',exact:true}).click();await expect(page.getByRole('button',{name:'管理下架',exact:true})).toBeVisible();await seller.reload();await expect(seller.locator('.panel-heading .tag')).toHaveText('已下架');
  seller.once('dialog',d=>d.accept());await seller.getByRole('button',{name:'重新上架',exact:true}).click();await expect(seller.locator('.panel-heading .tag')).toHaveText('在售');
  await guest.reload();await expect(guest.getByRole('heading',{name:original.title,exact:true})).toBeVisible();await page.screenshot({path:path.resolve('../../.local/logs/goods/admin.png'),fullPage:true});
  await manager.close();await owner.close();await visitor.close();
});

test('数据库故障时保留商品表单和暂存图片，恢复后可保存',async({page})=>{
  test.skip(!enabled);await login(page,process.env.GOODS_ALICE);await page.goto('/goods/new');
  const title='故障恢复商品'+suffix;await page.getByLabel('商品标题',{exact:true}).fill(title);await page.getByLabel('商品描述',{exact:true}).fill('故障时保留商品描述');await page.getByLabel('价格（元）',{exact:true}).fill('12.34');await upload(page);
  const root=path.resolve('../..'),compose=['compose','--env-file',path.join(root,'deploy/.env'),'-f',path.join(root,'deploy/compose.dev.yaml')];let stopped=false;
  try{execFileSync('docker',[...compose,'stop','mysql'],{cwd:root,stdio:'pipe',timeout:60000});stopped=true;await page.getByRole('button',{name:'发布商品',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'服务暂时不可用'})).toBeVisible({timeout:25000});await expect(page.getByLabel('商品标题',{exact:true})).toHaveValue(title);await expect(page.getByLabel('价格（元）',{exact:true})).toHaveValue('12.34');await expect(page.locator('.upload-list li')).toHaveCount(1);expect(new URL(page.url()).pathname).toBe('/goods/new');await page.screenshot({path:path.resolve('../../.local/logs/goods/database-failure.png'),fullPage:true});}
  finally{if(stopped)execFileSync('docker',[...compose,'up','-d','--wait','--wait-timeout','120'],{cwd:root,stdio:'pipe',timeout:150000});}
  await expect.poll(async()=>{try{return(await page.request.get('/health/ready')).status();}catch{return 0;}},{timeout:30000}).toBe(200);await page.getByRole('button',{name:'发布商品',exact:true}).click();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();await expect(page.locator('.goods-detail-price')).toContainText('12.34');
});
