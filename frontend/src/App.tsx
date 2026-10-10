import { useState } from "react";
import type { Order, StartCallResult } from "./api";
import OrdersPage from "./components/OrdersPage";
import CallScreen from "./components/CallScreen";
import CallLog from "./components/CallLog";

type Tab = "orders" | "log";

export default function App() {
  const [tab, setTab] = useState<Tab>("orders");
  const [active, setActive] = useState<{ order: Order; start: StartCallResult } | null>(null);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          Zari Collective <span>COD confirmation agent</span>
        </div>
        {!active && (
          <nav>
            <button className={tab === "orders" ? "tab active" : "tab"} onClick={() => setTab("orders")}>
              Orders
            </button>
            <button className={tab === "log" ? "tab active" : "tab"} onClick={() => setTab("log")}>
              Call log
            </button>
          </nav>
        )}
      </header>

      <main>
        {active ? (
          <CallScreen
            order={active.order}
            start={active.start}
            onExit={() => {
              setActive(null);
              setTab("orders");
            }}
          />
        ) : tab === "orders" ? (
          <OrdersPage onCallStarted={(order, start) => setActive({ order, start })} />
        ) : (
          <CallLog />
        )}
      </main>
    </div>
  );
}