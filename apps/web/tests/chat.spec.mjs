import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
test.use({trace:'off'});test.setTimeout(180000);
const enabled=process.env.E2E_CHAT==='1',suffix=process.env.CHAT_SUFFIX||'unused';
async function login(page,account){await page.goto('/login');await page.getByLabel('账号',{exact:true}).fill(account);await page.getByLabel('密码',{exact:true}).fill(process.env.CHAT_PASSWORD||'');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL(/\/profile$/);}
function frames(page){const seen=[];page.on('websocket',socket=>{expect(socket.url()).not.toContain('?');socket.on('framereceived',event=>{try{seen.push(JSON.parse(String(event.payload)));}catch{}});});return seen;}
async function postMessage(page,cid,body){const protection=await(await page.request.get('/api/v1/csrf')).json();const response=await page.request.post(`/api/v1/conversations/${cid}/messages`,{headers:{Origin:process.env.WEB_ORIGIN||'http://localhost:3000','X-CSRF-Token':protection.data.csrf_token},data:{client_message_id:crypto.randomUUID(),body}});expect(response.status()).toBe(201);return(await response.json()).data;}

test('商品联系卖家、双浏览器真实实时消息、历史与窄屏',async({browser})=>{
  test.skip(!enabled);const buyer=await browser.newContext(),seller=await browser.newContext(),a=await buyer.newPage(),b=await seller.newPage();const received=frames(b),errors=[];a.on('pageerror',e=>errors.push(e.message));b.on('pageerror',e=>errors.push(e.message));
  await login(a,process.env.CHAT_BOB);await login(b,process.env.CHAT_ALICE);await a.goto('/goods/'+process.env.CHAT_GOODS);await a.getByRole('button',{name:'联系卖家',exact:true}).click();await expect(a).toHaveURL(new RegExp('/messages/'+process.env.CHAT_CONVERSATION+'$'));
  await b.goto('/messages/'+process.env.CHAT_CONVERSATION);await expect(b.getByRole('status').filter({hasText:'实时连接正常'})).toBeVisible();
  const body='浏览器实时消息'+suffix+' <script>window.chatInjected=true</script>';await a.getByLabel('文字消息',{exact:true}).fill(body);await a.getByRole('button',{name:'发送消息',exact:true}).click();
  await expect(a.locator('.chat-message').filter({hasText:body})).toHaveCount(1);await expect(b.locator('.chat-message').filter({hasText:body})).toHaveCount(1);await expect.poll(()=>received.some(frame=>frame.type==='message.created'&&frame.data.body===body)).toBe(true);
  expect(await b.evaluate(()=>window.chatInjected)).toBeUndefined();await b.getByLabel('文字消息',{exact:true}).fill('卖家回复'+suffix);await b.getByRole('button',{name:'发送消息',exact:true}).click();await expect(a.locator('.chat-message').filter({hasText:'卖家回复'+suffix})).toHaveCount(1);
  await a.reload();await expect(a.locator('.chat-message').filter({hasText:body})).toHaveCount(1);if(await a.getByRole('button',{name:'加载更早消息',exact:true}).isVisible()){await a.getByRole('button',{name:'加载更早消息',exact:true}).click();}
  await a.setViewportSize({width:375,height:812});expect(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await a.screenshot({path:path.resolve('../../.local/logs/chat/chat-mobile.png'),fullPage:true});expect(errors).toEqual([]);
  await buyer.close();await seller.close();
});

test('离线失败保留待发消息，重连补读与重试不重复',async({browser})=>{
  test.skip(!enabled);const buyer=await browser.newContext(),seller=await browser.newContext(),a=await buyer.newPage(),b=await seller.newPage();await login(a,process.env.CHAT_BOB);await login(b,process.env.CHAT_ALICE);const cid=process.env.CHAT_CONVERSATION;await a.goto('/messages/'+cid);await expect(a.getByLabel('文字消息',{exact:true})).toBeVisible();
  await buyer.setOffline(true);await a.getByRole('button',{name:'重新连接',exact:true}).click();
  // Keep the already loaded page; explicitly reconnecting closes its old live connection.
  const text='离线待重试'+suffix;await a.getByLabel('文字消息',{exact:true}).fill(text);await a.getByRole('button',{name:'发送消息',exact:true}).click();await expect(a.getByRole('button',{name:'重试发送',exact:true})).toBeVisible({timeout:20000});await expect(a.getByLabel('文字消息',{exact:true})).toHaveValue(text);
  const incoming='离线期间的新消息'+suffix;await postMessage(b,cid,incoming);
  await buyer.setOffline(false);if(await a.getByRole('button',{name:'重新连接',exact:true}).isVisible())await a.getByRole('button',{name:'重新连接',exact:true}).click();await expect(a.locator('.chat-message').filter({hasText:incoming})).toHaveCount(1,{timeout:15000});
  await a.getByRole('button',{name:'重试发送',exact:true}).click();await expect(a.locator('.chat-message').filter({hasText:text})).toHaveCount(1);await a.getByRole('button',{name:'补读最新消息',exact:true}).click();await expect(a.locator('.chat-message').filter({hasText:text})).toHaveCount(1);
  const saved=(await(await a.request.get(`/api/v1/conversations/${cid}/messages?after_sequence=0&limit=100`)).json()).data.items;expect(saved.filter(m=>m.body===text)).toHaveLength(1);await buyer.close();await seller.close();
});

test('通知已读持久化、私聊成员限制与同会话退出联动',async({browser})=>{
  test.skip(!enabled);const buyer=await browser.newContext(),third=await browser.newContext(),manager=await browser.newContext(),page=await buyer.newPage(),outsider=await third.newPage(),admin=await manager.newPage();await login(page,process.env.CHAT_BOB);await page.goto('/notifications');await expect(page.getByRole('heading',{name:'站内通知',exact:true})).toBeVisible();await expect(page.locator('body')).not.toContainText('隐藏后不能泄漏的标题');
  await expect(page.locator('.notification-list li').first()).toBeVisible();await page.screenshot({path:path.resolve('../../.local/logs/chat/notifications-list.png'),fullPage:true});
  await page.getByRole('button',{name:'全部标为已读',exact:true}).click();await expect(page.getByText('未读 0 条',{exact:true})).toBeVisible();await page.getByLabel('只看未读',{exact:true}).click();await expect(page.getByLabel('只看未读',{exact:true})).toBeChecked();await expect(page).toHaveURL(/unread_only=true/);await expect(page.getByText('暂无未读通知。',{exact:true})).toBeVisible();await page.reload();await expect(page.getByText('未读 0 条',{exact:true})).toBeVisible();await expect(page.getByText('暂无未读通知。',{exact:true})).toBeVisible();await page.screenshot({path:path.resolve('../../.local/logs/chat/notifications.png'),fullPage:true});
  await login(outsider,process.env.CHAT_THIRD);await outsider.goto('/messages/'+process.env.CHAT_CONVERSATION);await expect(outsider.getByRole('alert').filter({hasText:'内容不存在'})).toBeVisible();await login(admin,process.env.CHAT_ADMIN);await admin.goto('/messages/'+process.env.CHAT_CONVERSATION);await expect(admin.getByRole('alert').filter({hasText:'内容不存在'})).toBeVisible();
  const other=await buyer.newPage();await other.goto('/messages/'+process.env.CHAT_CONVERSATION);await expect(other.getByLabel('文字消息',{exact:true})).toBeVisible();await page.getByRole('button',{name:'退出',exact:true}).click();await expect(other.getByRole('heading',{name:'请先登录',exact:true})).toBeVisible({timeout:5000});
  await buyer.close();await third.close();await manager.close();
});

test('数据库故障不显示发送成功，恢复后同一待发消息可保存',async({page})=>{
  test.skip(!enabled);await login(page,process.env.CHAT_BOB);const cid=process.env.CHAT_CONVERSATION;await page.goto('/messages/'+cid);const text='数据库故障保留消息'+suffix;await page.getByLabel('文字消息',{exact:true}).fill(text);
  const root=path.resolve('../..'),compose=['compose','--env-file',path.join(root,'deploy/.env'),'-f',path.join(root,'deploy/compose.dev.yaml')];let stopped=false;
  try{execFileSync('docker',[...compose,'stop','mysql'],{cwd:root,stdio:'pipe',timeout:60000});stopped=true;await page.getByRole('button',{name:'发送消息',exact:true}).click();await expect(page.getByRole('button',{name:'重试发送',exact:true})).toBeVisible({timeout:25000});await expect(page.getByLabel('文字消息',{exact:true})).toHaveValue(text);await expect(page.locator('.chat-message').filter({hasText:text})).toHaveCount(0);await page.screenshot({path:path.resolve('../../.local/logs/chat/database-failure.png'),fullPage:true});}
  finally{if(stopped)execFileSync('docker',[...compose,'up','-d','--wait','--wait-timeout','120'],{cwd:root,stdio:'pipe',timeout:150000});}
  await expect.poll(async()=>{try{return(await page.request.get('/health/ready')).status();}catch{return 0;}},{timeout:30000}).toBe(200);await page.getByRole('button',{name:'重试发送',exact:true}).click();await expect(page.locator('.chat-message').filter({hasText:text})).toHaveCount(1,{timeout:20000});
});
