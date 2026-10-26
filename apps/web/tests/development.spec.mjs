import {test, expect} from '@playwright/test';
import path from 'node:path';

test('保存后刷新仍可读取，文字按普通内容显示，窄屏不横向溢出', async ({page}) => {
  test.skip(process.env.E2E_FAILURE_MODE === '1');
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const body = `浏览器保存 ${Date.now()} <script>window.injected=true</script>`;
  await page.goto('/dev-check');
  await expect(page.getByText('服务已就绪', {exact: true})).toBeVisible();
  await page.getByLabel('测试内容').fill(body);
  await page.getByRole('button', {name: '保存记录', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('已保存');
  await expect(page.getByText(body, {exact: true})).toBeVisible();
  await expect(page.getByLabel('测试内容')).toHaveValue('');
  await page.reload();
  await expect(page.getByText(body, {exact: true})).toBeVisible();
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  await page.screenshot({path: path.resolve('../../.local/logs/dev/desktop.png'), fullPage: true});
  await page.setViewportSize({width: 375, height: 812});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: path.resolve('../../.local/logs/dev/mobile.png'), fullPage: true});
  expect(errors).toEqual([]);
});

test('真实数据库停机时保存失败、保留输入且不显示成功', async ({page}) => {
  test.skip(process.env.E2E_FAILURE_MODE !== '1');
  await page.goto('/dev-check');
  await expect(page.getByText('依赖尚未就绪', {exact: true})).toBeVisible({timeout: 15000});
  const body = `数据库故障时保留输入 ${Date.now()}`;
  await page.getByLabel('测试内容').fill(body);
  await page.getByRole('button', {name: '保存记录', exact: true}).click();
  await expect(page.getByRole('alert').filter({hasText: '暂时无法保存'})).toBeVisible();
  await expect(page.getByLabel('测试内容')).toHaveValue(body);
  await expect(page.getByRole('status')).toHaveCount(0);
  await page.screenshot({path: path.resolve('../../.local/logs/dev/database-failure.png'), fullPage: true});
});
