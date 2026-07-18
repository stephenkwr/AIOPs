import type { components } from "./schema";

import { api } from "./client";

export type DemoSeedResult = components["schemas"]["DemoSeedResult"];

/** Load the Aurora support KB into the demo workspace (idempotent). */
export async function seedDemo(): Promise<DemoSeedResult> {
  const { data, error } = await api.POST("/api/v1/demo/seed");
  if (error || !data) throw new Error("Failed to load demo data");
  return data;
}
