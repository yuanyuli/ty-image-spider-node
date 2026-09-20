// 旧描述符与新来源统一使用同一组回退规则。
export function normalizePresentation(descriptor = {}) {
  const value = descriptor?.presentation || {};
  return {
    groupId: value.group_id || "other",
    groupLabel: value.group_label || "其他",
    shortLabel: value.short_label || descriptor?.label || descriptor?.id || "来源",
    detailLabel: value.detail_label || descriptor?.label || descriptor?.id || "来源",
    groupOrder: Number.isFinite(value.group_order) ? value.group_order : 999,
    sourceOrder: Number.isFinite(value.source_order) ? value.source_order : 999,
    cacheDescription:
      value.cache_description ||
      "按当前搜索条件续存最多100张新素材，跳过已有缓存；不足时按实际数量完成",
    visible: value.visible !== false,
  };
}

export function visibleSources(providers) {
  return providers
    .filter((entry) => normalizePresentation(entry.provider).visible)
    .sort(
      (a, b) =>
        normalizePresentation(a.provider).sourceOrder -
        normalizePresentation(b.provider).sourceOrder,
    );
}

export function sourceGroups(providers) {
  const groups = new Map();
  for (const entry of providers) {
    const value = normalizePresentation(entry.provider);
    if (!groups.has(value.groupId))
      groups.set(value.groupId, {
        id: value.groupId,
        label: value.groupLabel,
        order: value.groupOrder,
      });
  }
  return [...groups.values()].sort((a, b) => a.order - b.order);
}
