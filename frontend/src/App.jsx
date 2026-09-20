import React, { useEffect, useRef, useState } from "react";
import { api } from "./api";

const TERMINAL_STATUSES = new Set(["DONE", "FAILED", "ROLLBACK"]);

export default function App() {
  const [task, setTask] = useState("Create a Python function that checks whether a number is prime");
  const [health, setHealth] = useState(null);
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRun, setActiveRun] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    refreshHealth();
    refreshRuns();
    const healthInterval = setInterval(refreshHealth, 15000);
    return () => clearInterval(healthInterval);
  }, []);

  useEffect(() => {
    if (!activeRunId) return;
    clearInterval(pollRef.current);

    const poll = async () => {
      try {
        const run = await api.getRun(activeRunId);
        setActiveRun(run);
        if (TERMINAL_STATUSES.has(run.status)) {
          clearInterval(pollRef.current);
          refreshRuns();
        }
      } catch (e) {
        setError(e.message);
        clearInterval(pollRef.current);
      }
    };

    poll();
    pollRef.current = setInterval(poll, 1500);
    return () => clearInterval(pollRef.current);
  }, [activeRunId]);

  async function refreshHealth() {
    try {
      setHealth(await api.health());
    } catch {
      setHealth({ ok: false, ollama_reachable: false, model: "" });
    }
  }

  async function refreshRuns() {
    try {
      setRuns(await api.listRuns());
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!task.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const { run_id } = await api.createRun(task.trim());
      setActiveRunId(run_id);
      setActiveRun(null);
      refreshRuns();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  const running = activeRun && !TERMINAL_STATUSES.has(activeRun.status);

  return (
    <div className="app">
      <header>
        <h1>AI Coding Orchestrator</h1>
        <p>Coder → Reviewer → Tester → Consensus → Retry / Rollback</p>
        <div className="health">
          <span className={`dot ${health?.ollama_reachable ? "ok" : ""}`} />
          {health?.ollama_reachable
            ? `Ollama reachable (${health.model})`
            : "Ollama not reachable — start `ollama serve` and pull the model"}
        </div>
      </header>

      <form className="panel" onSubmit={handleSubmit}>
        <p className="section-title">Task</p>
        <div className="task-row">
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe the coding task…"
            rows={2}
          />
          <button type="submit" disabled={submitting || running}>
            {running ? "Running…" : "Run Task"}
          </button>
        </div>
        {error && <p style={{ color: "var(--red)", fontSize: 13, marginTop: 10 }}>{error}</p>}
      </form>

      <div className="grid-2">
        <div className="panel">
          <p className="section-title">Execution timeline</p>
          {!activeRun && <p className="empty">Run a task to see its timeline here.</p>}
          {activeRun && (
            <>
              <span className={`status-pill ${activeRun.status}`}>{activeRun.status}</span>
              <div className="timeline" style={{ marginTop: 12 }}>
                {activeRun.events.map((ev, i) => (
                  <div className="timeline-item" key={i}>
                    <span className={`badge ${ev.state}`}>{ev.state}</span>
                    <span>{ev.message}</span>
                  </div>
                ))}
                {activeRun.events.length === 0 && <p className="empty">Waiting for first event…</p>}
              </div>
              {activeRun.error && (
                <p style={{ color: "var(--red)", fontSize: 13, marginTop: 12 }}>{activeRun.error}</p>
              )}
            </>
          )}
        </div>

        <div className="panel">
          <p className="section-title">Recent runs</p>
          <div className="run-history">
            {runs.length === 0 && <p className="empty">No runs yet.</p>}
            {runs.map((r) => (
              <div
                key={r.run_id}
                className={`run-row ${r.run_id === activeRunId ? "active" : ""}`}
                onClick={() => setActiveRunId(r.run_id)}
              >
                <span className="task-snippet">{r.task}</span>
                <span className={`status-pill ${r.status}`} style={{ fontSize: 10 }}>
                  {r.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {activeRun?.final_code && (
        <div className="panel">
          <p className="section-title">
            Generated code {activeRun.rolled_back && <span className="muted">(rolled back to last checkpoint)</span>}
          </p>
          <pre>{activeRun.final_code}</pre>
        </div>
      )}

      {activeRun?.final_tests && (
        <div className="panel">
          <p className="section-title">Generated tests</p>
          <pre>{activeRun.final_tests}</pre>
        </div>
      )}
    </div>
  );
}
