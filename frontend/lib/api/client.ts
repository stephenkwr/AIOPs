import createClient from "openapi-fetch";

import type { paths } from "./schema";

// The backend base URL. Overridden per-environment via NEXT_PUBLIC_API_BASE_URL.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Typed client generated from the backend's OpenAPI schema. GET/DELETE/etc. are
// fully type-checked against the real API contract — a backend change that breaks
// the contract shows up as a TypeScript error here, not a runtime surprise.
export const api = createClient<paths>({ baseUrl: API_BASE_URL });
