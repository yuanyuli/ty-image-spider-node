import { readFileSync } from "node:fs";

const descriptors = JSON.parse(
  readFileSync(new URL("./fixtures/provider_descriptors.json", import.meta.url), "utf8"),
);

export function sourceDescriptor(id) {
  return structuredClone(descriptors[id] || { id, label: id });
}
