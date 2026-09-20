// Node 20 在 Windows 上不展开测试通配符，显式传入文件列表。
import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

const tests = readdirSync("tests")
  .filter((name) => name.endsWith(".test.mjs"))
  .sort()
  .map((name) => `tests/${name}`);
const result = spawnSync(process.execPath, ["--test", ...tests], {
  stdio: "inherit",
});
process.exit(result.error ? 1 : result.status ?? 1);
