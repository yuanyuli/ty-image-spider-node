// 每个节点独立跟踪各来源任务；关闭节点只清理轮询，不取消服务器工作。
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
    onUpdate(job);
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
      onError(error, slot.provider);
      if (error.status === 404)
        publish(slot, { ...slot.job, state: "failed", message: "缓存任务已过期，请重新启动" });
      else queue(slot);
    }
  }

  return {
    get(provider) {
      return slots.get(provider)?.job || null;
    },
    async start(payload) {
      if (disposed) return;
      let slot = slots.get(payload.provider);
      if (slot?.pending || slot?.job?.state === "running") return;
      slot = { provider: payload.provider, pending: true, job: null, timer: null };
      slots.set(payload.provider, slot);
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
        if (!disposed) onError(error, payload.provider);
      } finally {
        slot.pending = false;
      }
    },
    async cancel(provider) {
      const slot = slots.get(provider);
      if (disposed || slot?.job?.state !== "running") return;
      try {
        publish(
          slot,
          await client.requestJson(`/ty-image-spider/cache/${slot.job.id}/cancel`, {
            method: "POST",
          }),
        );
      } catch (error) {
        if (!disposed) onError(error, provider);
      }
    },
    dispose() {
      disposed = true;
      for (const slot of slots.values()) unschedule(slot.timer);
      slots.clear();
    },
  };
}
