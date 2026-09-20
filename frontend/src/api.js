const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  createRun: (task) => request("/runs", { method: "POST", body: JSON.stringify({ task }) }),
  getRun: (runId) => request(`/runs/${runId}`),
  listRuns: () => request("/runs"),
};
