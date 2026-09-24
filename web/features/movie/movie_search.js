import { openMoviePicker } from "./movie_picker.js";

export function createMovieSearch({ document, client, openPicker = openMoviePicker }) {
  let active = null;
  return {
    cancel() {
      active?.close();
      active = null;
    },
    async search(payload, isCurrent) {
      let request = payload;
      for (let step = 0; step < 3; step += 1) {
        const page = await client.requestJson("/ty-image-spider/search", {
          method: "POST",
          body: request,
        });
        if (!isCurrent()) return null;
        if (!page.choices?.length) return page;
        const picker = openPicker({ document, page });
        active = picker;
        const selection = await picker.result;
        if (active === picker) active = null;
        if (!selection || !isCurrent()) return null;
        request = { ...request, cursor: null, filters: { ...request.filters, ...selection } };
      }
      throw new Error("电影版本尚未确认，请重新搜索");
    },
  };
}
