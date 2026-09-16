import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, createApiClient } from "../web/api.js";

test("API 客户端解析统一成功响应", async () => {
  const calls = [];
  const api = createApiClient(async (path, options) => {
    calls.push([path, options]);
    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true, data: { items: [1] } };
      },
    };
  });

  const data = await api.requestJson("/ty-image-spider/search", {
    method: "POST",
    body: { provider: "local" },
  });

  assert.deepEqual(data, { items: [1] });
  assert.equal(calls[0][1].headers["Content-Type"], "application/json");
  assert.equal(calls[0][1].body, '{"provider":"local"}');
});

test("API 客户端保留后端错误结构", async () => {
  const api = createApiClient(async () => ({
    ok: false,
    status: 503,
    async json() {
      return {
        ok: false,
        error: { code: "opencli_missing", message: "未找到", action: "请安装" },
      };
    },
  }));

  await assert.rejects(
    api.requestJson("/providers"),
    (error) =>
      error instanceof ApiError &&
      error.code === "opencli_missing" &&
      error.action === "请安装" &&
      error.status === 503,
  );
});

test("API 客户端拒绝不可解析的响应", async () => {
  const api = createApiClient(async () => ({
    ok: true,
    status: 200,
    async json() {
      throw new Error("bad json");
    },
  }));

  await assert.rejects(api.requestJson("/providers"), /无法读取/);
});
