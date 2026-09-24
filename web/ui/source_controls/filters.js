import { element } from "../../core/dom.js";

export function renderField(document, field, supplied, onFilterChange, options = {}) {
  const wrapper = element(document, "label", `tyis-filter tyis-filter-${field.kind}`);
  const label = element(document, "span", "tyis-filter-label", field.label);
  const value = supplied ?? field.default;
  let control;
  if (field.kind === "select") {
    control = element(document, "select", "tyis-field");
    for (const option of field.options || []) {
      const node = element(document, "option", "", option.label);
      node.value = option.value;
      control.append(node);
    }
    control.value = value ?? "";
  } else if (field.kind === "toggle") {
    wrapper.classList.add("tyis-toggle");
    control = element(document, "input", "tyis-toggle-input");
    control.type = "checkbox";
    control.checked = Boolean(value);
  } else {
    control = element(document, "input", "tyis-field");
    control.type = field.kind === "number" ? "number" : "text";
    control.value = value ?? "";
    if (field.minimum !== undefined) control.min = String(field.minimum);
    if (field.maximum !== undefined) control.max = String(field.maximum);
    if (field.placeholder) control.placeholder = field.placeholder;
  }
  control.name = field.name;
  control.disabled = Boolean(options.disabled);
  control.addEventListener("change", () => {
    const next =
      field.kind === "toggle"
        ? control.checked
        : field.kind === "number"
          ? Number(control.value)
          : control.value;
    onFilterChange(field.name, next);
  });
  if (field.kind === "toggle") wrapper.append(control, label);
  else wrapper.append(label, control);
  return wrapper;
}
