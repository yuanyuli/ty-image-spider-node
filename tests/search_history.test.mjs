import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createSearchHistory } from "../web/search_history.js";

test("最近关键词按来源保存并去重，且不保存笔记链接", () => {
  const { localStorage } = new JSDOM("", { url: "https://localhost/" }).window;
  const history = createSearchHistory(localStorage);

  history.add("xiaohongshu", "秋季穿搭");
  history.add("civitai", "portrait");
  history.add("xiaohongshu", "摄影");
  history.add("xiaohongshu", "秋季穿搭");
  history.add("xiaohongshu", "https://www.xiaohongshu.com/explore/abc?xsec_token=secret");

  assert.deepEqual(history.list("xiaohongshu"), ["秋季穿搭", "摄影"]);
  assert.deepEqual(history.list("civitai"), ["portrait"]);
  assert.doesNotMatch(localStorage.getItem("ty-image-spider:search-history"), /xsec_token/);
});
