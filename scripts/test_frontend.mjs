// Node 20 在 Windows 上不展开测试通配符，显式传入文件列表。
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

const tests = findFiles("tests", (path) => path.endsWith(".test.mjs"));
const result = spawnSync(process.execPath, ["--test", ...tests], {
  stdio: "inherit",
});
process.exit(result.error ? 1 : result.status ?? 1);
