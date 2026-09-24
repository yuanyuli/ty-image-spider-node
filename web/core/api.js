export class ApiError extends Error {
  constructor(code, message, action = "", status = 0, details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.action = action;
    this.status = status;
    this.details = details;
  }
}

export function createApiClient(fetchApi) {
  if (typeof fetchApi !== "function") throw new TypeError("fetchApi 必须是函数");

  return {
    async requestJson(path, options = {}) {
      const request = { ...options, headers: { ...(options.headers || {}) } };
      if (request.body !== undefined && typeof request.body !== "string") {
        request.headers["Content-Type"] = "application/json";
        request.body = JSON.stringify(request.body);
      }

      const response = await fetchApi(path, request);
      let envelope;
      try {
        envelope = await response.json();
      } catch (_) {
        throw new ApiError(
          "invalid_response",
          "服务返回了无法读取的数据，请检查 ComfyUI 后端",
          "",
          response.status,
        );
      }
      if (!response.ok || envelope?.ok !== true) {
        const error = envelope?.error || {};
        throw new ApiError(
          error.code || "request_failed",
          error.message || `请求失败（${response.status}）`,
          error.action || "",
          response.status,
          error.details || {},
        );
      }
      return envelope.data;
    },
  };
}
