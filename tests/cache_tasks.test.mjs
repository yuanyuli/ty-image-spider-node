import assert from "node:assert/strict";
import test from "node:test";

test("切换来源仍保存各自的缓存任务，取消和轮询只作用于指定任务", async () => {
  const { createCacheTasks } = await import("../web/cache_tasks.js");
  const cancelled = [];
  const scheduled = new Map();
  let serial = 0;
  const jobs = new Map();
  const client = {
    async requestJson(path, options) {
      if (path.endsWith("/start")) {
        const job = {
          id: String(++serial),
          provider: options.body.provider,
          state: "running",
          cached: 0,
        };
        jobs.set(job.id, job);
        return job;
      }
      const id = path.split("/")[3];
      if (path.endsWith("/cancel")) {
        cancelled.push(id);
        jobs.get(id).state = "cancelled";
      }
      return { ...jobs.get(id) };
    },
  };
  const view = createCacheTasks({
    client,
    schedule: (fn) => {
      const id = Symbol();
      scheduled.set(id, fn);
      return id;
    },
    unschedule: (id) => scheduled.delete(id),
  });
  await view.start({ provider: "a" });
  await view.start({ provider: "b" });
  assert.equal(view.get("a").id, "1");
  assert.equal(view.get("b").id, "2");
  await view.cancel("a");
  assert.deepEqual(cancelled, ["1"]);
  assert.equal(view.get("b").state, "running");
  for (const fn of [...scheduled.values()]) await fn();
  assert.equal(view.get("a").state, "cancelled");
  view.dispose();
  assert.equal(scheduled.size, 0);
});

test("重复任务接管已有任务 ID，移除节点后迟到响应不再安排轮询", async () => {
  const { createCacheTasks } = await import("../web/cache_tasks.js");
  let respond;
  let scheduled = 0;
  const updates = [];
  const view = createCacheTasks({
    client: {
      async requestJson(path) {
        if (path.endsWith("/start"))
          throw { code: "cache_duplicate", details: { job_id: "existing" } };
        return new Promise((resolve) => {
          respond = resolve;
        });
      },
    },
    schedule: () => ++scheduled,
    unschedule: () => {},
    onUpdate: (job) => updates.push(job),
  });
  const start = view.start({ provider: "a" });
  await Promise.resolve();
  view.dispose();
  respond({ id: "existing", provider: "a", state: "running" });
  await start;
  assert.equal(scheduled, 0);
  assert.equal(updates.length, 0);
});
