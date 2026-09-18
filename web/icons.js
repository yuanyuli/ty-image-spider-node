const ICONS = {
  search: [
    ["circle", { cx: 11, cy: 11, r: 8 }],
    ["path", { d: "m21 21-4.3-4.3" }],
  ],
  refresh: [
    ["path", { d: "M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5" }],
    ["path", { d: "M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5" }],
  ],
  next: [["path", { d: "m9 18 6-6-6-6" }]],
  previous: [["path", { d: "m15 18-6-6 6-6" }]],
  download: [
    ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" }],
    ["path", { d: "m7 10 5 5 5-5" }],
    ["path", { d: "M12 15V3" }],
  ],
  copy: [
    ["rect", { width: 14, height: 14, x: 8, y: 8, rx: 2, ry: 2 }],
    ["path", { d: "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" }],
  ],
  "external-link": [
    ["path", { d: "M15 3h6v6" }],
    ["path", { d: "M10 14 21 3" }],
    ["path", { d: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" }],
  ],
  close: [
    ["path", { d: "M18 6 6 18" }],
    ["path", { d: "m6 6 12 12" }],
  ],
  reset: [
    ["path", { d: "M3 7v6h6" }],
    ["path", { d: "M21 17v-6h-6" }],
    ["path", { d: "M20 11A8 8 0 0 0 5.4 7.5L3 13" }],
    ["path", { d: "M4 13a8 8 0 0 0 14.6 3.5L21 11" }],
  ],
  chevron: [["path", { d: "m9 18 6-6-6-6" }]],
};

export function createIcon(document, name, size = 18) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("tyis-icon");
  for (const [tag, attributes] of ICONS[name] || ICONS.chevron) {
    const child = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) child.setAttribute(key, String(value));
    svg.append(child);
  }
  return svg;
}

export function createIconButton(document, name, label, className = "tyis-icon-button") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.title = label;
  button.setAttribute("aria-label", label);
  button.append(createIcon(document, name));
  return button;
}
