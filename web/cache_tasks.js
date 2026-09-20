// 每个节点按来源、查询和筛选独立跟踪任务。
export function cacheTaskKey(payload) {
  if (typeof payload === "string") payload = { provider: payload };
  function sorted(value) {
    if (Array.isArray(value)) return value.map(sorted);
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, sorted(value[key])]),
      );
    return value;
  }
  return JSON.stringify(
    sorted({
      provider: payload.provider,
      query: (payload.query || "").trim(),
      filters: payload.filters || {},
    }),
  );
}

// 关闭节点只清理轮询，不取消服务器工作。
export function createCacheTasks({
  client,
  onUpdate = () => {},
  onError = () => {},
  schedule = setTimeout,
  unschedule = clearTimeout,
}) {
  const slots = new Map();
  let disposed = false;

  function publish(slot, job) {
    if (disposed) return;
    slot.job = job;
    onUpdate(job, slot.key);
    if (job.state === "running") queue(slot);
  }

  function queue(slot) {
    if (disposed) return;
    unschedule(slot.timer);
    slot.timer = schedule(() => poll(slot), 750);
  }

  async function poll(slot) {
    if (disposed || slot.job?.state !== "running") return;
    try {
      publish(slot, await client.requestJson(`/ty-image-spider/cache/${slot.job.id}`));
    } catch (error) {
      if (disposed) return;
      onError(error, slot.key);
      if (error.status === 404)
        publish(slot, { ...slot.job, state: "failed", message: "缓存任务已过期，请重新启动" });
      else queue(slot);
    }
  }

  return {
    get(payload) {
      return slots.get(cacheTaskKey(payload))?.job || null;
    },
    async start(payload) {
      if (disposed) return;
      const key = cacheTaskKey(payload);
      let slot = slots.get(key);
      if (slot?.pending || slot?.job?.state === "running") return;
      slot = { key, pending: true, job: null, timer: null };
      slots.set(key, slot);
      try {
        let job;
        try {
          job = await client.requestJson("/ty-image-spider/cache/start", {
            method: "POST",
            body: payload,
          });
        } catch (error) {
          if (error.code !== "cache_duplicate" || !error.details?.job_id) throw error;
          if (disposed) return;
          job = await client.requestJson(`/ty-image-spider/cache/${error.details.job_id}`);
        }
        publish(slot, job);
      } catch (error) {
        if (!disposed) onError(error, key);
      } finally {
        slot.pending = false;
      }
    },
    async cancel(payload) {
      const slot = slots.get(cacheTaskKey(payload));
      if (disposed || slot?.job?.state !== "running") return;
      try {
        publish(
          slot,
          await client.requestJson(`/ty-image-spider/cache/${slot.job.id}/cancel`, {
            method: "POST",
          }),
        );
      } catch (error) {
        if (!disposed) onError(error, slot.key);
      }
    },
    dispose() {
      disposed = true;
      for (const slot of slots.values()) unschedule(slot.timer);
      slots.clear();
    },
  };
}
