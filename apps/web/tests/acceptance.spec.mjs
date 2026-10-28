import {test, expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import path from 'node:path';

test.use({trace: 'off'});
test.setTimeout(150000);
const enabled = process.env.E2E_ACCEPTANCE === '1';
const suffix = process.env.ACC_SUFFIX || 'unused';
const output = path.resolve('../../.local/logs/acceptance');

async function login(page, account) {
  await page.goto('/login');
  await page.getByLabel('账号', {exact: true}).fill(account);
  await page.getByLabel('密码', {exact: true}).fill(process.env.ACC_PASSWORD || '');
  await page.getByRole('button', {name: '登录', exact: true}).click();
  await expect(page).toHaveURL(/\/profile$/);
}

async function mutate(page, url, method, data) {
  const protection = await (await page.request.get('/api/v1/csrf')).json();
  const response = await page.request.fetch(url, {method, data, headers: {
    Origin: process.env.WEB_ORIGIN || 'http://localhost:3000',
    'X-CSRF-Token': protection.data.csrf_token,
  }});
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}

test('同一批数据完成发帖回复、商品搜索、卖家私聊和通知已读', async ({browser}) => {
  test.skip(!enabled);
  const seller = await browser.newContext(), buyer = await browser.newContext();
  const a = await seller.newPage(), b = await buyer.newPage();
  const errors = [], received = [];
  for (const page of [a, b]) page.on('pageerror', error => errors.push(error.message));
  a.on('websocket', socket => socket.on('framereceived', event => {
    try {received.push(JSON.parse(String(event.payload)));} catch {}
  }));
  await login(a, process.env.ACC_ALICE);
  await login(b, process.env.ACC_BOB);
  const keyword = '完整流程' + suffix, postTitle = keyword + '交流帖', goodsTitle = keyword + '闲置平板';
  await a.getByRole('link', {name: '论坛', exact: true}).click();
  await a.getByRole('link', {name: '发布帖子', exact: true}).last().click();
  await a.getByLabel('标题', {exact: true}).fill(postTitle);
  await a.getByLabel('正文', {exact: true}).fill('同一批数据的联通检查。');
  await a.getByLabel('上传图片', {exact: true}).setInputFiles(process.env.ACC_PNG);
  await expect(a.locator('.upload-list li')).toHaveCount(1);
  await expect(a.getByRole('status').filter({hasText: '正在处理文件'})).toHaveCount(0);
  await a.getByRole('button', {name: '发布帖子', exact: true}).click();
  await expect(a.getByRole('heading', {name: postTitle, exact: true})).toBeVisible();
  const postId = new URL(a.url()).pathname.split('/').pop();
  await b.goto('/posts/' + postId);
  await b.getByLabel('写回复', {exact: true}).fill('买家的真实回复' + suffix);
  await b.getByRole('button', {name: '提交回复', exact: true}).click();
  await expect(b.getByRole('status')).toContainText('回复已保存');
  await b.getByRole('button', {name: '点赞', exact: true}).click();
  await b.getByRole('button', {name: '收藏', exact: true}).click();
  await b.reload();
  await expect(b.getByRole('button', {name: '取消点赞', exact: true})).toBeVisible();
  await expect(b.getByRole('button', {name: '取消收藏', exact: true})).toBeVisible();
  await expect(b.getByText('买家的真实回复' + suffix, {exact: true})).toBeVisible();

  await a.getByRole('link', {name: '商品', exact: true}).click();
  await a.getByRole('link', {name: '发布商品', exact: true}).last().click();
  await a.getByLabel('商品标题', {exact: true}).fill(goodsTitle);
  await a.getByLabel('商品描述', {exact: true}).fill('图书馆自提，联通检查的模拟商品。');
  await a.getByLabel('交易校区', {exact: true}).selectOption('shahe');
  await a.getByLabel('价格（元）', {exact: true}).fill('123.451');
  await a.getByLabel('上传图片', {exact: true}).setInputFiles(process.env.ACC_PNG);
  await expect(a.locator('.upload-list li')).toHaveCount(1);
  await expect(a.getByRole('status').filter({hasText: '正在处理文件'})).toHaveCount(0);
  await a.getByRole('button', {name: '发布商品', exact: true}).click();
  await expect(a.getByRole('alert').filter({hasText: '最多两位小数'})).toBeVisible();
  await a.getByLabel('价格（元）', {exact: true}).fill('123.45');
  await a.getByRole('button', {name: '发布商品', exact: true}).click();
  await expect(a.getByRole('heading', {name: goodsTitle, exact: true})).toBeVisible();
  const goodsId = new URL(a.url()).pathname.split('/').pop();
  await b.getByRole('link', {name: '搜索', exact: true}).click();
  await b.getByLabel('关键词', {exact: true}).fill(keyword);
  await b.getByRole('button', {name: '搜索', exact: true}).click();
  await expect(b.locator('.search-results li')).toHaveCount(2);
  await expect(b.getByRole('link', {name: postTitle, exact: true})).toBeVisible();
  await b.getByLabel('内容类型', {exact: true}).selectOption('goods');
  await b.getByLabel('交易校区', {exact: true}).selectOption('shahe');
  await b.getByLabel('最高价格（元）', {exact: true}).fill('123.45');
  await b.getByRole('button', {name: '搜索', exact: true}).click();
  await expect(b.locator('.search-results li')).toHaveCount(1);
  const filtered = new URL(b.url()).search;
  await b.getByRole('link', {name: goodsTitle, exact: true}).click();
  await b.getByRole('link', {name: '← 返回列表', exact: true}).click();
  await expect.poll(() => new URL(b.url()).search).toBe(filtered);
  await b.getByRole('link', {name: goodsTitle, exact: true}).click();
  await b.getByRole('button', {name: '联系卖家', exact: true}).click();
  await expect(b).toHaveURL(/\/messages\/\d+$/);
  const cid = new URL(b.url()).pathname.split('/').pop();
  await a.goto('/messages/' + cid);
  await expect(a.getByRole('status').filter({hasText: '实时连接正常'})).toBeVisible();
  const text = '跨板块流程中的私聊' + suffix;
  await b.getByLabel('文字消息', {exact: true}).fill(text);
  await b.getByRole('button', {name: '发送消息', exact: true}).click();
  await expect(a.locator('.chat-message').filter({hasText: text})).toHaveCount(1);
  await expect.poll(() => received.some(frame => frame.type === 'message.created' && frame.data.body === text)).toBe(true);
  await b.reload();
  await expect(b.locator('.chat-message').filter({hasText: text})).toHaveCount(1);
  await b.getByRole('link', {name: '站内通知', exact: true}).click();
  const notice = b.locator(`[data-notification-id="${process.env.ACC_SYSTEM_NOTICE}"]`);
  await expect(notice).toContainText('联通测试通知');
  await notice.getByRole('button', {name: '标为已读', exact: true}).click();
  await expect(notice.getByText('未读', {exact: true})).toHaveCount(0);
  await b.reload();
  await expect(notice).toBeVisible();
  await expect(notice.getByText('未读', {exact: true})).toHaveCount(0);
  await b.setViewportSize({width: 375, height: 812});
  expect(await b.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await b.screenshot({path: path.join(output, 'flow-notifications-mobile.png'), fullPage: true});
  writeFileSync(path.join(output, 'flow-ids.json'), JSON.stringify({postId, goodsId, cid}));
  expect(errors).toEqual([]);
  await seller.close();await buyer.close();
});

test('加载、空内容、无权限和读写失败可恢复，失败不冒充保存', async ({page}) => {
  test.skip(!enabled);
  await page.goto('/messages');
  await expect(page.getByRole('heading', {name: '请先登录', exact: true})).toBeVisible();
  await page.goto('/search?q=' + encodeURIComponent('不存在的内容' + suffix));
  await expect(page.locator('.search-results li')).toHaveCount(0);
  await expect(page.getByText('没有符合条件的结果，可调整关键词或筛选条件。', {exact: true})).toBeVisible();
  const matcher = /\/api\/v1\/goods(?:\?.*)?$/;
  let release;
  const gate = new Promise(resolve => {release = resolve;});
  await page.route(matcher, async route => {
    await gate;
    await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({
      error: {code: 'SERVICE_UNAVAILABLE', message: '联通测试读失败'}, meta: {request_id: crypto.randomUUID()},
    })});
  });
  await page.goto('/goods');
  await expect(page.getByText('正在读取…', {exact: true}).first()).toBeVisible();
  release();
  await expect(page.getByRole('alert').filter({hasText: '联通测试读失败'})).toBeVisible();
  await page.unroute(matcher);
  await page.getByRole('button', {name: '重试读取', exact: true}).click();
  await expect(page.getByRole('link', {name: process.env.ACC_MANAGED_GOODS, exact: true})).toBeVisible();
  await login(page, process.env.ACC_THIRD);
  await page.goto('/admin/goods');
  await expect(page.getByRole('heading', {name: '没有访问权限', exact: true})).toBeVisible();
  await page.goto('/messages/' + process.env.ACC_MANAGED_CID);
  await expect(page.getByRole('alert').filter({hasText: '内容不存在'})).toBeVisible();
  await page.goto('/posts/new');
  const title = '失败不得保存' + suffix;
  await page.getByLabel('标题', {exact: true}).fill(title);
  await page.getByLabel('正文', {exact: true}).fill('读取失败与保存失败分开检查。');
  const postRoute = /\/api\/v1\/posts$/;
  await page.route(postRoute, route => route.request().method() === 'POST'
    ? route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({
      error: {code: 'SERVICE_UNAVAILABLE', message: '联通测试保存失败'}, meta: {request_id: crypto.randomUUID()},
    })}) : route.continue());
  await page.getByRole('button', {name: '发布帖子', exact: true}).click();
  await expect(page.getByRole('alert').filter({hasText: '联通测试保存失败'})).toBeVisible();
  await expect(page.getByLabel('标题', {exact: true})).toHaveValue(title);
  await expect(page).toHaveURL(/\/posts\/new$/);
  expect((await (await page.request.get('/api/v1/search?q=' + encodeURIComponent(title))).json()).data.total).toBe(0);
  await page.unroute(postRoute);
  await page.getByRole('button', {name: '发布帖子', exact: true}).click();
  await expect(page.getByRole('heading', {name: title, exact: true})).toBeVisible();
  const browser = page.context().browser(), routes = [];
  for (const [account, targets] of [
    [process.env.ACC_ALICE, ['/', '/posts', '/posts/new', '/posts/' + process.env.ACC_POST,
      '/posts/' + process.env.ACC_POST + '/edit', '/me/posts', '/me/favorites', '/goods', '/goods/new',
      '/goods/' + process.env.ACC_GOODS, '/goods/' + process.env.ACC_GOODS + '/edit', '/me/goods',
      '/me/goods/' + process.env.ACC_GOODS, '/search?q=' + encodeURIComponent('管理联动' + suffix),
      '/messages', '/messages/' + process.env.ACC_MANAGED_CID, '/notifications']],
    [process.env.ACC_ADMIN, ['/admin/users', '/admin/posts', '/admin/posts/' + process.env.ACC_POST,
      '/admin/goods', '/admin/goods/' + process.env.ACC_GOODS]],
  ]) {
    const context = await browser.newContext({viewport: {width: 375, height: 812}});
    const current = await context.newPage();await login(current, account);
    for (const target of targets) {
      await current.goto(target);
      await expect(current.locator('main h1').first()).toBeVisible();
      await expect(current.locator('main')).not.toContainText('请先登录');
      await expect(current.locator('main')).not.toContainText('没有访问权限');
      await expect(current.getByRole('alert').filter({hasText: '内容不存在'})).toHaveCount(0);
      expect(await current.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      routes.push({path: target, role: account === process.env.ACC_ADMIN ? 'admin' : 'owner', width: 375, status: 'passed'});
    }
    await context.close();
  }
  for (const target of ['/posts/18446744073709551615', '/goods/18446744073709551615']) {
    await page.goto(target);
    await expect(page.getByRole('alert').filter({hasText: '内容不存在'})).toBeVisible();
  }
  writeFileSync(path.join(output, 'page-coverage.json'), JSON.stringify(routes));
});

test('一次管理操作同步影响搜索、旧文件、聊天来源与通知', async ({browser}) => {
  test.skip(!enabled);
  const buyer = await browser.newContext(), manager = await browser.newContext();
  const page = await buyer.newPage(), admin = await manager.newPage();
  await login(page, process.env.ACC_BOB);await login(admin, process.env.ACC_ADMIN);
  await page.goto('/notifications');
  const notice = page.locator(`[data-notification-id="${process.env.ACC_GOODS_NOTICE}"]`);
  await expect(notice).toContainText('当前状态：在售');
  const post = (await (await admin.request.get('/api/v1/admin/posts/' + process.env.ACC_POST)).json()).data;
  const goods = (await (await admin.request.get('/api/v1/admin/goods/' + process.env.ACC_GOODS)).json()).data;
  await mutate(admin, '/api/v1/admin/posts/' + post.id + '/moderation', 'PATCH', {action: 'hide', version: post.version, reason: '跨功能隐藏检查'});
  await mutate(admin, '/api/v1/admin/goods/' + goods.id + '/moderation', 'PATCH', {action: 'restrict', version: goods.version, reason: '跨功能限制检查'});
  await page.reload();
  await expect(notice).toContainText('相关内容当前不可访问');
  await expect(page.locator('.notification-list')).not.toContainText(process.env.ACC_MANAGED_GOODS);
  await expect(page.locator('.notification-list')).not.toContainText(process.env.ACC_MANAGED_POST);
  await page.goto('/search?q=' + encodeURIComponent('管理联动' + suffix));
  await expect(page.locator('.search-results li')).toHaveCount(0);
  await expect(page.getByText('没有符合条件的结果，可调整关键词或筛选条件。', {exact: true})).toBeVisible();
  expect((await page.request.get(process.env.ACC_POST_FILE)).status()).toBe(404);
  expect((await page.request.get(process.env.ACC_GOODS_FILE)).status()).toBe(404);
  await page.goto('/messages/' + process.env.ACC_MANAGED_CID);
  await expect(page.getByText('来源商品当前不可用，已有聊天仍可读取。', {exact: true})).toBeVisible();
  await expect(page.locator('body')).not.toContainText(process.env.ACC_MANAGED_GOODS);
  expect((await admin.request.get('/api/v1/conversations/' + process.env.ACC_MANAGED_CID)).status()).toBe(404);
  await page.screenshot({path: path.join(output, 'moderation-context.png'), fullPage: true});
  await buyer.close();await manager.close();
});
