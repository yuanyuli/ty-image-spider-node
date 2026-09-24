// 逐个检查浏览器模块语法，不依赖 Shell 通配符展开。
import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

function findFiles(root, accept) {
  return readdirSync(root, { withFileTypes: true })
    .flatMap((entry) => {
      const path = `${root}/${entry.name}`;
      if (entry.isDirectory()) {
        return entry.name === "node_modules" ? [] : findFiles(path, accept);
      }
      return accept(path) ? [path] : [];
    })
    .sort();
}

for (const file of findFiles("web", (path) => path.endsWith(".js"))) {
  const result = spawnSync(process.execPath, ["--check", file], {
    stdio: "inherit",
  });
  if (result.error || result.status !== 0) process.exit(result.status || 1);
}
