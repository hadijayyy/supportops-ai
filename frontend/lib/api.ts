import type { AgentResult, Demo, Evaluation } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const getDemos = () => api<Demo[]>("/api/customers/demo");
export const getEvaluation = () => api<Evaluation>("/api/evaluations/latest");
export const runAgent = (message: string, customerId: string, demoMode = true) =>
  api<AgentResult>("/api/agent/run", {
    method: "POST",
    body: JSON.stringify({ message, customer_id: customerId, demo_mode: demoMode }),
  });
