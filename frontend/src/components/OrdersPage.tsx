import { useEffect, useState } from "react";
import { api, errorText, playAudio, type Order, type StartCallResult } from "../api";
import StatusBadge from "./StatusBadge";

const CALLABLE = ["PENDING", "NEEDS_REVIEW", "NOT_CONFIRMED"];

interface Props {
  onCallStarted: (order: Order, start: StartCallResult) => void;
}

export default function OrdersPage({ onCallStarted }: Props) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    try {
      setOrders(await api.orders());
      setError("");
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function addDemoOrders() {
    try {
      await api.demoOrders();
      await load();
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function startCall(order: Order) {
    setBusyId(order.id);
    try {
      const start = await api.startCall(order.id);
      playAudio(start.audio_url);
      onCallStarted(order, start);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <div className="section-head">
        <h2>Orders</h2>
        <div className="actions">
          <button onClick={load}>Refresh</button>
          <button onClick={addDemoOrders}>Add demo orders</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <table>
        <thead>
          <tr>
            <th>#</th><th>Customer</th><th>Items</th><th>Amount</th><th>City</th><th>Status</th><th></th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td>{o.customer_name}</td>
              <td>{o.items}</td>
              <td>Rs {o.amount.toLocaleString()}</td>
              <td>{o.city}</td>
              <td><StatusBadge status={o.status} /></td>
              <td>
                {CALLABLE.includes(o.status) && (
                  <button className="primary" disabled={busyId !== null} onClick={() => startCall(o)}>
                    {busyId === o.id ? "Calling…" : "Call"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {orders.length === 0 && !error && <p className="muted">No orders yet. Click "Add demo orders".</p>}
    </section>
  );
}