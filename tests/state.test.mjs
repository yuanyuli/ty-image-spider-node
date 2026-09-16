import assert from "node:assert/strict";
import test from "node:test";

import { createRequestGuard, createSpiderState, serializeWorkflowState } from "../web/state.js";

test("小红书持久状态移除结果和签名链接", () => {
  const saved = serializeWorkflowState({
    provider: "xiaohongshu",
    filters: { query: "穿搭" },
    items: [
      {
        source_url: "https://www.xiaohongshu.com/explore/a?xsec_token=secret",
      },
    ],
  });

  assert.deepEqual(JSON.parse(saved), {
    provider: "xiaohongshu",
    filters: { query: "穿搭" },
  });
  assert.equal(saved.includes("xsec_token"), false);
});

test("普通来源可以恢复结果但会移除未定义字段", () => {
  const saved = serializeWorkflowState({
    provider: "civitai",
    filters: { query: "cat", tag: undefined },
    items: [{ id: "1", title: undefined }],
    summary: undefined,
  });

  assert.deepEqual(JSON.parse(saved), {
    provider: "civitai",
    filters: { query: "cat" },
    items: [{ id: "1" }],
  });
});

test("状态容器按补丁更新并通知订阅者", () => {
  const state = createSpiderState({ provider: "local" });
  const snapshots = [];
  const unsubscribe = state.subscribe((value) => snapshots.push(value.provider));

  state.set({ provider: "civitai" });
  unsubscribe();
  state.set({ provider: "xiaohongshu" });

  assert.equal(state.get().provider, "xiaohongshu");
  assert.deepEqual(snapshots, ["civitai"]);
});

test("过期请求不能覆盖新搜索", () => {
  const guard = createRequestGuard();
  const old = guard.begin();
  const current = guard.begin();

  assert.equal(guard.isCurrent(old), false);
  assert.equal(guard.isCurrent(current), true);
  guard.invalidate();
  assert.equal(guard.isCurrent(current), false);
});
