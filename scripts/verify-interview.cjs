const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'http://127.0.0.1:5173';
const SHOTS = path.join(__dirname, '.playwright-mcp');

if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });

function shot(page, name) {
  return page.screenshot({ path: path.join(SHOTS, name), fullPage: false });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('=== Step 1: Login ===');
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.fill('input[type="text"]', 'test@example.com');
  await page.fill('input[type="password"]', 'Test123456');
  await page.click('button:has-text("登录")');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
  console.log('Logged in -> dashboard');
  await shot(page, '01-dashboard.png');

  console.log('=== Step 2: Go to interview new ===');
  await page.goto(`${BASE}/interview/new`, { waitUntil: 'networkidle' });
  await shot(page, '02-setup-form.png');

  console.log('=== Step 3: Fill and start ===');
  await page.fill('text="例如：高级前端工程师"', '高级前端工程师');
  await page.fill('text="例如：字节跳动"', '字节跳动');
  await page.click('button:has-text("开始面试")');
  await shot(page, '03-after-click.png');

  // Wait for the live interview page to appear
  await page.waitForSelector('text=AI 面试官', { timeout: 15000 });
  console.log('Live interview page loaded');
  await shot(page, '04-live-page.png');

  // Wait for WebSocket connection (check for "已连接" or wait a bit)
  await page.waitForTimeout(3000);
  const sidebarText = await page.textContent('aside');
  console.log('Sidebar text:', sidebarText?.substring(0, 300));
  const connected = sidebarText?.includes('已连接') || !sidebarText?.includes('未连接');
  console.log('WS connected:', connected ? 'YES ✅' : 'NO ❌');
  await shot(page, '05-ws-status.png');

  console.log('=== Step 4: Type self-intro ===');
  const textarea = page.locator('textarea');
  await textarea.fill('你好，我是张浩然，有5年前端开发经验，目前在某互联网公司担任高级前端工程师。我的核心项目是从0到1设计并落地了EdgeKit内部微前端框架，已在公司6个产品中使用，体积相比qiankun减少40%。我擅长React生态、TypeScript以及前端工程化。');
  await shot(page, '06-typed-intro.png');

  console.log('=== Step 5: Submit self-intro ===');
  await page.click('button:has-text("发送")');
  console.log('Submitted');

  // Wait for AI response (the first question)
  await page.waitForTimeout(5000);
  await shot(page, '07-after-first-submit.png');

  // Wait longer for LLM to respond
  console.log('Waiting for AI question...');
  try {
    await page.waitForSelector('text=第 1 题', { timeout: 60000 });
    console.log('AI question received! ✅');
  } catch {
    console.log('Timed out waiting for question - checking page state');
    const pageText = await page.textContent('main');
    console.log('Page content:', pageText?.substring(0, 500));
  }
  await shot(page, '08-question-received.png');

  console.log('=== Step 6: Answer first question ===');
  await textarea.fill('EdgeKit的沙箱隔离机制主要包含两层：JS层面我们采用了基于Proxy的变量拦截沙箱，通过with语句+Proxy结合的方式限制全局变量的读写；CSS层面使用Shadow DOM实现样式隔离。在多实例场景下我们使用快照-恢复机制，每个子应用有一个独立的沙箱实例。性能上我们做了懒激活优化，非活跃子应用的沙箱会自动休眠。');
  await page.click('button:has-text("发送")');
  console.log('Submitted answer 1');

  await page.waitForTimeout(8000);
  await shot(page, '09-after-answer1.png');

  // Check for score feedback
  const pageText2 = await page.textContent('main');
  const hasScore = pageText2?.includes('评分') || pageText2?.includes('/10');
  console.log('Has score feedback:', hasScore ? 'YES ✅' : 'checking...');

  // Answer a few more questions if possible
  for (let i = 2; i <= 5; i++) {
    console.log(`=== Step ${5+i}: Answer question ${i} ===`);
    const textarea2 = page.locator('textarea');
    const isEnabled = await textarea2.isEnabled().catch(() => false);
    if (!isEnabled) {
      console.log('Textarea not enabled, waiting...');
      await page.waitForTimeout(10000);
    }

    await textarea2.fill(`这是我对第${i}道题的回答。我会从问题背景、技术方案选型、核心实现细节和效果验证几个方面来回答。在实际项目中我们遇到过相关的挑战，通过团队协作和深入的技术调研，最终找到了合适的解决方案。具体的实现过程中，我们重点关注了性能、可维护性和扩展性，并且通过量化的指标来验证效果。`);
    await page.click('button:has-text("发送")');
    console.log(`Submitted answer ${i}`);
    await page.waitForTimeout(8000);
    await shot(page, `10-after-answer${i}.png`);
  }

  // Final screenshot
  await shot(page, '99-final.png');

  console.log('=== DONE ===');
  await browser.close();
})().catch(e => {
  console.error('ERROR:', e.message);
  process.exit(1);
});
