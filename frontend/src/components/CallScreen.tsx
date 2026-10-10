import { useState, type FormEvent } from "react";
import {
  api, audioSrc, errorText, playAudio,
  type Latency, type Order, type RetryResult, type StartCallResult, type TurnResult,
} from "../api";
import { useRecorder } from "../useRecorder";
import StatusBadge from "./StatusBadge";

interface Message {
  speaker: "agent" | "customer";
  text: string;
  audioUrl?: string;
  intent?: string;
  latency?: Latency;
}

interface Props {
  order: Order;
  start: StartCallResult;
  onExit: () => void;
}

function latencyText(l?: Latency): string {
  if (!l) return "";
  const parts: string[] = [];
  if (l.asr_ms) parts.push(`ASR ${l.asr_ms}`);
  if (l.llm_ms) parts.push(`LLM ${l.llm_ms}`);
  if (l.tts_ms) parts.push(`TTS ${l.tts_ms}`);
  const total = l.total_ms ?? l.tts_ms;
  return parts.length ? `${parts.join(" + ")}${total ? ` = ${total} ms` : ""}` : "";
}

export default function CallScreen({ order, start, onExit }: Props) {
  const callId = start.call_id;
  const [messages, setMessages] = useState<Message[]>([
    { speaker: "agent", text: start.reply, audioUrl: start.audio_url, latency: start.latency },
  ]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<{ outcome: string | null; needsReview: boolean } | null>(null);
  const recorder = useRecorder();

  function handle(res: TurnResult | RetryResult) {
    if ("retry" in res) {
      setNotice(res.message);
      return;
    }
    setNotice("");
    setMessages((m) => [
      ...m,
      { speaker: "customer", text: res.heard, intent: res.intent },
      { speaker: "agent", text: res.reply, audioUrl: res.audio_url, latency: res.latency },
    ]);
    playAudio(res.audio_url);
    if (res.ended) setResult({ outcome: res.outcome, needsReview: res.needs_review });
  }

  async function run(task: () => Promise<TurnResult | RetryResult>) {
    setBusy(true);
    try {
      handle(await task());
    } catch (e) {
      setNotice(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    setText("");
    await run(() => api.sendText(callId, t));
  }

  async function onMic() {
    if (!recorder.recording) {
      try {
        await recorder.start();
        setNotice("Recording… speak, then press the button again to send.");
      } catch {
        setNotice("Microphone not available, or permission was denied.");
      }
      return;
    }
    const blob = await recorder.stop();
    setNotice("");
    await run(() => api.sendAudio(callId, blob));
  }

  return (
    <section className="call">
      <div className="section-head">
        <div>
          <h2>Call #{callId}</h2>
          <p className="muted">
            {order.customer_name} · Rs {order.amount.toLocaleString()} · {order.city}
          </p>
        </div>
        <button onClick={onExit}>← Back to orders</button>
      </div>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.speaker}`}>
            <div className="msg-head">
              {m.speaker === "agent" ? "Agent (سارہ)" : "Customer"}
              {m.intent && <span className="intent">{m.intent}</span>}
            </div>
            <p dir="auto" className="msg-text">{m.text}</p>
            {m.audioUrl && <audio controls src={audioSrc(m.audioUrl)} />}
            {m.latency && <div className="latency">{latencyText(m.latency)}</div>}
          </div>
        ))}
        {busy && <div className="msg agent thinking">…</div>}
      </div>

      {notice && <div className="notice">{notice}</div>}

      {result ? (
        <div className="result">
          Call ended: <StatusBadge status={result.outcome} />
          {result.needsReview && <span className="badge badge-needs_review">flagged for review</span>}
          <button className="primary" onClick={onExit}>Back to orders</button>
        </div>
      ) : (
        <div className="controls">
          <button
            className={recorder.recording ? "mic recording" : "mic"}
            disabled={busy}
            onClick={onMic}
          >
            {recorder.recording ? "⏹ Stop & send" : "🎙 Speak"}
          </button>
          <form onSubmit={onSubmit} className="text-form">
            <input
              dir="auto"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="…or type the customer's reply (Urdu / Roman Urdu / English)"
              disabled={busy || recorder.recording}
            />
            <button type="submit" disabled={busy || recorder.recording || !text.trim()}>Send</button>
          </form>
        </div>
      )}
    </section>
  );
}