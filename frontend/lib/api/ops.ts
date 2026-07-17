import type { components } from "./schema";

import { api } from "./client";

export type Escalation = components["schemas"]["EscalationOut"];

export async function listEscalations(): Promise<Escalation[]> {
  const { data, error } = await api.GET("/api/v1/escalations");
  if (error || !data) throw new Error("Failed to load escalations");
  return data;
}
