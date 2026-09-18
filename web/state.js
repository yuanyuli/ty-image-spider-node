const DEFAULT_STATE = Object.freeze({
  provider: "civitai",
  filters: {},
  items: [],
  summary: undefined,
  nextCursor: null,
  currentCursor: null,
  previousCursors: [],
  loading: false,
  error: null,
});

export function createSpiderState(initial = {}) {
  let value = {
    ...DEFAULT_STATE,
    ...initial,
    filters: { ...(initial.filters || {}) },
    previousCursors: [...(initial.previousCursors || [])],
  };
  const listeners = new Set();

  return {
    get() {
      return value;
    },
    set(patch) {
      value = { ...value, ...patch };
      for (const listener of listeners) listener(value);
      return value;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

const EMPTY_SESSION = Object.freeze({
  filters: { query: "" },
  items: [],
  summary: undefined,
  nextCursor: null,
  currentCursor: null,
  previousCursors: [],
  error: null,
});

export function createProviderSessions() {
  const values = new Map();
  return {
    save(provider, state) {
      values.set(provider, cloneSession(state));
    },
    load(provider) {
      return cloneSession(values.get(provider) || EMPTY_SESSION);
    },
  };
}

function cloneSession(value) {
  return {
    filters: { ...(value.filters || EMPTY_SESSION.filters) },
    items: [...(value.items || EMPTY_SESSION.items)],
    summary: value.summary,
    nextCursor: value.nextCursor ?? null,
    currentCursor: value.currentCursor ?? null,
    previousCursors: [...(value.previousCursors || [])],
    error: value.error ?? null,
  };
}

export function serializeWorkflowState(state) {
  const value = {
    provider: state.provider,
    filters: state.filters,
    summary: state.summary,
    nextCursor: state.nextCursor,
    currentCursor: state.currentCursor,
    previousCursors: state.previousCursors,
  };
  if (state.provider !== "xiaohongshu") value.items = state.items;
  return JSON.stringify(removeUndefined(stripSensitive(value)));
}

export function createRequestGuard() {
  let revision = 0;
  return {
    begin() {
      revision += 1;
      return revision;
    },
    invalidate() {
      revision += 1;
    },
    isCurrent(ticket) {
      return ticket === revision;
    },
  };
}

function stripSensitive(value) {
  if (typeof value === "string") {
    return /(?:xsec_token|authorization|cookie)=/i.test(value) ? undefined : value;
  }
  if (Array.isArray(value)) {
    return value.map(stripSensitive).filter((item) => item !== undefined);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !/(token|secret|cookie|authorization)/i.test(key))
        .map(([key, item]) => [key, stripSensitive(item)]),
    );
  }
  return value;
}

function removeUndefined(value) {
  if (Array.isArray(value)) return value.map(removeUndefined);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([, item]) => item !== undefined)
        .map(([key, item]) => [key, removeUndefined(item)]),
    );
  }
  return value;
}
