import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { createMovieSearch } from "../web/movie_search.js";
import { openMoviePicker } from "../web/movie_picker.js";

test("弹窗反向 Tab 跳过折叠帮助中的链接", () => {
  const dom = new JSDOM("<body></body>");
  const document = dom.window.document;
  const picker = openMoviePicker({ document, page: { choices: [] } });
  document.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", { key: "Tab", shiftKey: true, cancelable: true }),
  );
  assert.equal(document.activeElement.tagName, "SUMMARY");
  picker.close();
});

test("候选选择沿用查询且下一次请求带电影身份，不修改原始筛选", async () => {
  const requests = [];
  const client = {
    async requestJson(path, options) {
      requests.push(options.body);
      return requests.length === 1
        ? { choices: [{ title: "低俗小说" }] }
        : { items: [{ id: "42-1" }] };
    },
  };
  const search = createMovieSearch({
    client,
    openPicker: () => ({ result: Promise.resolve({ tmdb_id: 680 }), close() {} }),
  });
  const payload = { provider: "filmgrab", query: "低俗小说", filters: {}, cursor: null };
  assert.equal((await search.search(payload, () => true)).items[0].id, "42-1");
  assert.deepEqual(requests[1].filters, { tmdb_id: 680 });
  assert.deepEqual(payload.filters, {});
});

test("过期请求不弹出候选框", async () => {
  const search = createMovieSearch({
    client: {
      async requestJson() {
        return { choices: [{}] };
      },
    },
    openPicker() {
      throw new Error("不应打开");
    },
  });
  assert.equal(await search.search({}, () => false), null);
});

test("取消选择关闭弹窗并恢复键盘焦点", async () => {
  const dom = new JSDOM('<button id="prior">搜索</button>');
  const document = dom.window.document;
  document.querySelector("button").focus();
  const picker = openMoviePicker({
    document,
    page: {
      message: "选择电影",
      choices: [
        {
          title: "低俗小说",
          subtitle: "1994",
          selection: { tmdb_id: 680 },
          poster_url: "javascript:alert(1)",
        },
      ],
    },
  });
  assert.equal(document.querySelector(".tyis-movie-choice img").hasAttribute("src"), false);
  document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(await picker.result, null);
  assert.equal(document.querySelector('[role="dialog"]'), null);
  assert.equal(document.activeElement.id, "prior");
});

test("候选卡片显示版本信息并返回选中 ID", async () => {
  const document = new JSDOM("<body></body>").window.document;
  const picker = openMoviePicker({
    document,
    page: { choices: [{ title: "沙丘", subtitle: "2021 · Dune", selection: { tmdb_id: 438631 } }] },
  });
  assert.match(document.body.textContent, /2021/);
  document.querySelector(".tyis-movie-choice button").click();
  assert.deepEqual(await picker.result, { tmdb_id: 438631 });
});
