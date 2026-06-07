const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const { chromium } = require(path.join(root, "frontend", "node_modules", "playwright"));
const outDir = path.join(root, "thesis_assets", "screenshots");
fs.mkdirSync(outDir, { recursive: true });

const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const baseUrl = "http://localhost:5173";

async function waitForApp(page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(700);
}

async function shot(page, name) {
  await waitForApp(page);
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    clip: { x: 0, y: 0, width: 1500, height: 800 },
  });
}

async function safeClick(page, selector) {
  const locator = page.locator(selector).first();
  await locator.waitFor({ state: "visible", timeout: 10000 });
  await locator.click();
}

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: edgePath });
  const context = await browser.newContext({
    viewport: { width: 1500, height: 800 },
    locale: "ru-RU",
  });
  const page = await context.newPage();

  await page.goto(baseUrl);
  await page.waitForSelector("text=Колледж экономики и техники");
  await shot(page, "01_public_home");

  await page.goto(`${baseUrl}/apply`);
  await page.waitForSelector("text=Расскажите о себе");
  await shot(page, "02_application_form");
  await page.fill('input[placeholder="12 цифр"]', "080203123456");
  await page.fill('input[type="date"]', "2008-02-03");
  await page.fill('input[placeholder="Фамилия Имя Отчество"]', "Иван Петров Сергеевич");
  await page.fill('input[type="email"]', "ivan.petrov@example.com");
  await page.fill('input[placeholder="+7 700 000 00 00"]', "+7 707 123 45 67");
  const createdResponse = page.waitForResponse((response) =>
    response.url().endsWith("/applications") && response.request().method() === "POST"
  );
  await safeClick(page, "button.form-submit");
  const created = await (await createdResponse).json();
  await page.evaluate((payload) => {
    localStorage.setItem(`cet_application_${payload.id}`, payload.public_token);
  }, created);
  await page.waitForSelector("text=Заявка отправлена");
  await shot(page, "03_application_success");
  await page.goto(`${baseUrl}/chat/${created.id}`);
  await page.waitForSelector("text=Чат по заявке");
  await page.fill('input[placeholder="Напишите сообщение..."]', "Здравствуйте, подскажите перечень документов для поступления.");
  await safeClick(page, "form.chat-input button");
  await page.waitForSelector("text=Здравствуйте, подскажите перечень документов");
  await shot(page, "04_public_chat");

  await page.goto(`${baseUrl}/admin/login`);
  await page.waitForSelector("text=Административный вход");
  await shot(page, "05_admin_login");
  await page.fill('input[type="email"]', "tech@cet.local");
  await page.fill('input[type="password"]', "admin12345");
  await safeClick(page, "button.primary-button");
  await page.waitForURL("**/admin/dashboard", { timeout: 15000 });
  await page.waitForSelector("text=Добро пожаловать");
  await shot(page, "06_admin_dashboard");

  await page.goto(`${baseUrl}/admin/applications`);
  await page.waitForSelector("text=Заявки и студенты");
  await page.waitForSelector(".data-table table tbody tr");
  await shot(page, "07_applications_registry");

  await page.locator(".data-table table tbody tr a").first().click();
  await page.waitForSelector("text=Основные данные");
  await shot(page, "08_application_details_main");
  await safeClick(page, "text=Приемная комиссия");
  await page.waitForSelector("text=Льготная группа");
  await shot(page, "09_application_details_admissions");

  await page.goto(`${baseUrl}/admin/file-manager`);
  await page.waitForSelector("text=Файловый менеджер");
  await page.waitForSelector(".folder-node");
  await shot(page, "10_file_manager");

  await page.goto(`${baseUrl}/admin/chats`);
  await page.waitForSelector("text=Чаты");
  await page.waitForTimeout(1200);
  await shot(page, "11_admin_chats");

  await page.goto(`${baseUrl}/admin/users`);
  await page.waitForSelector("text=Пользователи и роли");
  await shot(page, "12_users_roles");

  await page.goto(`${baseUrl}/admin/settings`);
  await page.waitForSelector("text=Системная информация");
  await shot(page, "13_settings");

  await browser.close();
})();
