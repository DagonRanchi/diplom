import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

const distDir = "dist";
const indexPath = join(distDir, "index.html");

if (!existsSync(indexPath)) {
  throw new Error("dist/index.html was not found");
}

const routes = [
  "apply",
  "applicant/login",
  "chat",
  "admin/login",
  "admin/dashboard",
  "admin/applications",
  "admin/contest",
  "admin/file-manager",
  "admin/chats",
  "admin/users",
  "admin/settings",
  "assistant/chats",
  "teacher/students",
];

copyFileSync(indexPath, join(distDir, "404.html"));

for (const route of routes) {
  const routeIndexPath = join(distDir, route, "index.html");
  mkdirSync(dirname(routeIndexPath), { recursive: true });
  copyFileSync(indexPath, routeIndexPath);
}
