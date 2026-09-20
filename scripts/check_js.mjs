// 逐个检查浏览器模块语法，不依赖 Shell 通配符展开。
import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

for (const file of readdirSync("web").filter((name) => name.endsWith(".js"))) {
  const result = spawnSync(process.execPath, ["--check", `web/${file}`], {
    stdio: "inherit",
  });
  if (result.error || result.status !== 0) process.exit(result.status || 1);
}
