import { useEffect, useState } from "react";
import { api, audioSrc, errorText, type CallDetail, type CallSummary } from "../api";
import StatusBadge from "./StatusBadge";

export default function CallLog() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [selected, setSelected] = useState<CallDetail | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setCalls(await api.calls());
      setError("");
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function open(id: number) {
    try {
      setSelected(await api.call(id));
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <section>
      <div className="section-head">
        <h2>Call log</h2>
        <button onClick={load}>Refresh</button>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="log">
        <div className="log-list">
          {calls.map((c) => (
            <button
              key={c.id}
              className={`log-item ${selected?.id === c.id ? "selected" : ""}`}
              onClick={() => open(c.id)}
            >
              <div>
                <strong>Call #{c.id}</strong> · {c.customer_name} · Rs {c.amount.toLocaleString()}
              </div>
              <div>
                <StatusBadge status={c.active ? "IN_PROGRESS" : c.outcome} />
                {c.needs_review ? <span className="badge badge-needs_review">review</span> : null}
              </div>
            </button>
          ))}
          {calls.length === 0 && !error && <p className="muted">No calls yet.</p>}
        </div>

        <div className="log-detail">
          {!selected ? (
            <p className="muted">Select a call to see its transcript, recordings and timings.</p>
          ) : (
            <>
              <h3>
                Call #{selected.id} · {selected.order.customer_name}{" "}
                <StatusBadge status={selected.active ? "IN_PROGRESS" : selected.outcome} />
              </h3>
              {selected.summary && <p className="muted">{selected.summary}</p>}
              {selected.review_reason && <div className="notice">Review: {selected.review_reason}</div>}

              {selected.turns.map((t) => (
                <div key={t.id} className={`msg ${t.speaker}`}>
                  <div className="msg-head">
                    {t.speaker === "agent" ? "Agent" : "Customer"}
                    {t.intent && <span className="intent">{t.intent}</span>}
                  </div>
                  <p dir="auto" className="msg-text">{t.text}</p>
                  {t.retrieved && (
                    <div className="rag">
                      RAG: “{t.retrieved.query}” → used{" "}
                      {t.retrieved.used.length ? t.retrieved.used.join(", ") : "nothing (escalated)"} · top match{" "}
                      {t.retrieved.hits[0]?.[0]} ({t.retrieved.hits[0]?.[1]})
                    </div>
                  )}
                  <div className="latency">
                    {[t.asr_ms && `ASR ${t.asr_ms} ms`, t.llm_ms && `LLM ${t.llm_ms} ms`, t.tts_ms && `TTS ${t.tts_ms} ms`]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                  {t.audio_url && <audio controls src={audioSrc(t.audio_url)} />}
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </section>
  );
}