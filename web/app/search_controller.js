export function createSearchController(context) {
  const {
    state,
    providers,
    gallery,
    guard,
    movieSearch,
    history,
    sessions,
    persist,
    setActivity,
    isDisposed,
  } = context;

  async function search(
    queryOverride,
    cursor = null,
    refresh = false,
    navigation = "reset",
    movieLookup = false,
  ) {
    const current = state.get();
    const source = providers().find((entry) => entry.provider.id === current.provider);
    if (source?.status?.available === false) {
      gallery()?.setUnavailable(source.status.message, source.status.action);
      setActivity(source.status.message || "素材源不可用", true);
      return;
    }
    const query = queryOverride === undefined ? current.filters.query || "" : queryOverride;
    if (queryOverride !== undefined) {
      state.set({ filters: { ...current.filters, query } });
      persist();
    }
    const ticket = guard.begin();
    movieSearch.cancel();
    const previousCursors = [...current.previousCursors];
    if (navigation === "next") previousCursors.push(current.currentCursor ?? null);
    else if (navigation === "previous") previousCursors.pop();
    else previousCursors.length = 0;
    gallery()?.setLoading(navigation !== "reset");
    setActivity("检索中");
    const { query: _ignored, ...filters } = state.get().filters;
    try {
      const page = await movieSearch.search(
        {
          provider: state.get().provider,
          query,
          filters: movieLookup ? { ...filters, movie_lookup: true } : filters,
          cursor,
          refresh,
        },
        () => guard.isCurrent(ticket) && !isDisposed(),
      );
      if (!guard.isCurrent(ticket) || isDisposed()) return;
      if (!page) {
        gallery()?.render(current.items || [], {
          next_cursor: current.nextCursor,
          has_previous: current.previousCursors.length > 0,
        });
        setActivity("已取消电影选择");
        return;
      }
      state.set({
        items: page.items || [],
        nextCursor: page.next_cursor || null,
        currentCursor: cursor,
        previousCursors,
        summary: { query, count: page.items?.length || 0, stale: Boolean(page.stale) },
        error: null,
      });
      history.add(current.provider, query);
      sessions.save(state.get().provider, state.get());
      gallery()?.render(state.get().items, {
        next_cursor: state.get().nextCursor,
        has_previous: state.get().previousCursors.length > 0,
      });
      setActivity(page.stale ? "缓存结果" : `${state.get().items.length} 项素材`);
      persist();
    } catch (error) {
      if (!guard.isCurrent(ticket) || isDisposed()) return;
      state.set({ error });
      const message = [error.message, error.action].filter(Boolean).join("。 ");
      gallery()?.setError(message);
      setActivity(message || "检索失败", true);
    }
  }

  return { search };
}
