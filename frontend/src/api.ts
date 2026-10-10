export const API = "http://localhost:8000";

// ---------- types: the shape of the data the backend sends ----------
export type OrderStatus = "PENDING" | "CONFIRMED" | "CANCELLED" | "NEEDS_REVIEW" | "NOT_CONFIRMED";

export interface Order {
  id: number;
  customer_name: string;
  phone: string;
  items: string;
  amount: number;
  city: string;
  address: string;
  status: OrderStatus;
  updated_at: string | null;
}

export interface Latency {
  asr_ms?: number;
  llm_ms?: number;
  tts_ms?: number;
  total_ms?: number;
}

export interface StartCallResult {
  call_id: number;
  reply: string;
  audio_url: string;
  latency: Latency;
}

export interface TurnResult {
  heard: string;
  reply: string;
  audio_url: string;
  intent: string;
  ended: boolean;
  outcome: string | null;
  needs_review: boolean;
  latency: Latency;
}

export interface RetryResult {
  retry: true;
  message: string;
}

interface CallRecord {
  id: number;
  order_id: number;
  started_at: string;
  ended_at: string | null;
  outcome: string | null;
  needs_review: number;
  review_reason: string | null;
  summary: string | null;
  active: boolean;
}

export interface CallSummary extends CallRecord {
  customer_name: string;
  amount: number;
}

export interface Retrieved {
  query: string;
  hits: [string, number][];
  used: string[];
}

export interface Turn {
  id: number;
  idx: number;
  speaker: "agent" | "customer";
  text: string;
  intent: string | null;
  retrieved: Retrieved | null;
  llm_ms: number | null;
  asr_ms: number | null;
  tts_ms: number | null;
  audio_url: string | null;
  created_at: string;
}

export interface CallDetail extends CallRecord {
  order: Order;
  turns: Turn[];
}

// ---------- helpers ----------
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response wasn't JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

function postJson(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function errorText(e: unknown): string {
  if (e instanceof TypeError) return "Can't reach the backend. Is the FastAPI server running on port 8000?";
  return e instanceof Error ? e.message : String(e);
}

export function audioSrc(url: string): string {
  return `${API}${url}`;
}

export function playAudio(url: string): void {
  new Audio(audioSrc(url)).play().catch(() => {
    /* browser blocked autoplay; the user can press play on the message */
  });
}

// ---------- the API calls ----------
export const api = {
  orders: () => request<Order[]>("/api/orders"),
  demoOrders: () => request<Order[]>("/api/demo/orders", { method: "POST" }),
  startCall: (orderId: number) => request<StartCallResult>("/api/calls", postJson({ order_id: orderId })),
  sendText: (callId: number, text: string) =>
    request<TurnResult>(`/api/calls/${callId}/text`, postJson({ text })),
  sendAudio: (callId: number, blob: Blob) => {
    const form = new FormData();
    const ext = blob.type.includes("ogg") ? "ogg" : "webm";
    form.append("file", blob, `reply.${ext}`);
    return request<TurnResult | RetryResult>(`/api/calls/${callId}/audio`, { method: "POST", body: form });
  },
  calls: () => request<CallSummary[]>("/api/calls"),
  call: (id: number) => request<CallDetail>(`/api/calls/${id}`),
};