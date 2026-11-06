const {chromium} = require('../apps/web/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const work = path.resolve(process.argv[2] || '.local/final412-02');
  const credentials = JSON.parse(fs.readFileSync(path.join(work, 'fixtures.json'), 'utf8'));
  const base = credentials.origin;
  assert.equal(base, 'https://youzhihui.85-121-122-124.sslip.io');
  const browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const result = {stage: '4.12', origin: base, checked_at: new Date().toISOString(), checks: [], status: 'running'};
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    await page.goto(base + '/login');
    await page.locator('#account').fill(credentials.buyer);
    await page.locator('#password').fill(credentials.password);
    await page.getByRole('button', {name: '登录', exact: true}).click();
    await page.waitForURL('**/profile');
    result.checks.push('Real production browser login');
    for (const [name, route, visible] of [
      ['post', '/posts/' + credentials.post_id, credentials.post_title],
      ['notifications', '/notifications', '商品匹配提醒'],
      ['task', '/me/subscriptions/' + credentials.task_id, '已暂停'],
      ['messages', '/messages', '课程验收412'],
    ]) {
      await page.goto(base + route);
      await page.getByText(visible, {exact: name === 'post'}).first().waitFor({timeout: 15000});
      await page.screenshot({path: path.join(work, name + '-desktop.png'), fullPage: true});
      result.checks.push('Browser reads ' + name);
    }
    await page.setViewportSize({width: 390, height: 844});
    for (const route of ['/me/subscriptions', '/notifications', '/posts/' + credentials.post_id]) {
      await page.goto(base + route);
      await page.waitForLoadState('networkidle');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.screenshot({path: path.join(work, 'post-mobile.png'), fullPage: true});
    result.checks.push('390px subscription/notification/post pages have no horizontal overflow');
    result.status = 'passed';
    console.log('PASS production browser login, post, notifications, paused task, messages, mobile layout');
  } catch (error) {
    result.status = 'failed';
    result.error = error.message;
    throw error;
  } finally {
    fs.mkdirSync('docs/final', {recursive: true});
    fs.writeFileSync('docs/final/browser-verification.json', JSON.stringify(result, null, 2) + '\n');
    await browser.close();
  }
})().catch(error => {console.error(error.message); process.exitCode = 1;});
