import json

from app import db, rag
from app.llm import json_call
from app.prompts import UNDERSTAND_SYSTEM, ANSWER_SYSTEM, STEP_DESCRIPTIONS, LINES

INTENTS = {"confirm", "cancel", "change_address", "question", "human", "deny", "end_call", "unclear"}
CALLABLE_STATUSES = {"PENDING", "NEEDS_REVIEW", "NOT_CONFIRMED"}
MIN_RAG_SCORE = 0.55
MAX_CUSTOMER_TURNS = 8
MAX_UNCLEAR = 2

ORDER_STATUS = {
    "CONFIRMED": "CONFIRMED",
    "CANCELLED": "CANCELLED",
    "ADDRESS_UPDATED": "CONFIRMED",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
    "NOT_CONFIRMED": "NOT_CONFIRMED",
}


class Call:
    def __init__(self, order_id):
        self.order = db.get_order(order_id)
        if self.order is None:
            raise ValueError(f"No order with id {order_id}")
        if self.order["status"] not in CALLABLE_STATUSES:
            raise ValueError(f"Order {order_id} is already {self.order['status']}")
        self.call_id = db.create_call(order_id)
        self.state = "ASK_CONFIRM"
        self.history = []
        self.turn_idx = 0
        self.customer_turns = 0
        self.unclear_count = 0
        self.pending_address = None
        self.cancel_reason = ""
        self.review_reasons = []
        self.outcome = None
        self.needs_review = False
        self.ended = False

    # ---------- helpers ----------
    def _log(self, speaker, text, intent=None, retrieved=None, llm_ms=None):
        self.history.append((speaker, text))
        db.add_turn(self.call_id, self.turn_idx, speaker, text, intent, retrieved, llm_ms)
        self.turn_idx += 1

    def _reprompt(self):
        if self.state == "ASK_NEW_ADDRESS":
            return LINES["ask_address"]
        if self.state == "READ_BACK":
            return LINES["read_back"].format(address=self.pending_address)
        if self.state == "ASK_CANCEL_REASON":
            return LINES["ask_reason"]
        return LINES["ask_again"]

    def _understand(self, text):
        o = self.order
        recent = "\n".join(f"{s}: {t}" for s, t in self.history[-6:])
        user = (
            f"Current step: {STEP_DESCRIPTIONS[self.state]}\n"
            f"Order: {o['items']}, Rs {o['amount']}, address: {o['address']}, {o['city']}\n"
            f"Recent conversation:\n{recent}\n\n"
            f"Customer just said: {text}"
        )
        data, ms = json_call(UNDERSTAND_SYSTEM, user)
        intent = data.get("intent", "unclear")
        if intent not in INTENTS:
            intent = "unclear"
        return {
            "intent": intent,
            "new_address": (data.get("new_address") or "").strip(),
            "cancel_reason": (data.get("cancel_reason") or "").strip(),
            "question": (data.get("question") or "").strip(),
        }, ms

    def _answer(self, question):
        hits = rag.search(question, k=3)
        log = {"query": question, "hits": [[h["id"], h["score"]] for h in hits], "used": []}
        if not hits or hits[0]["score"] < MIN_RAG_SCORE:
            return None, json.dumps(log, ensure_ascii=False), 0
        context = "\n".join(f"[{h['id']}] {h['text']}" for h in hits)
        data, ms = json_call(ANSWER_SYSTEM, f"Context:\n{context}\n\nCustomer question: {question}")
        log["used"] = data.get("used_ids", [])
        answer = (data.get("answer") or "").strip()
        if data.get("answerable") is True and answer:
            return answer, json.dumps(log, ensure_ascii=False), ms
        return None, json.dumps(log, ensure_ascii=False), ms

    def _start_address_change(self, address):
        if address:
            self.pending_address = address
            self.state = "READ_BACK"
            return LINES["read_back"].format(address=address)
        self.state = "ASK_NEW_ADDRESS"
        return LINES["ask_address"]

    def _end(self, outcome, line, reason=None):
        if reason:
            self.review_reasons.append(reason)
        self.needs_review = outcome == "NEEDS_REVIEW" or bool(self.review_reasons)
        new_address = self.pending_address if outcome == "ADDRESS_UPDATED" else None
        db.update_order(self.order["id"], ORDER_STATUS[outcome], new_address)

        parts = [outcome]
        if outcome == "CANCELLED":
            parts.append(f"reason: {self.cancel_reason or 'not given'}")
        if outcome == "ADDRESS_UPDATED":
            parts.append(f"new address: {self.pending_address}")
        if outcome == "NOT_CONFIRMED":
            parts.append("customer ended the call; follow up or auto-cancel after 24h")
        if self.review_reasons:
            parts.append("review: " + "; ".join(self.review_reasons))
        db.end_call(self.call_id, outcome, self.needs_review,
                    "; ".join(self.review_reasons) or None, " | ".join(parts))

        self.outcome, self.ended = outcome, True
        return line

    # ---------- the decision logic ----------
    def _decide(self, intent, u, text):
        if self.customer_turns > MAX_CUSTOMER_TURNS:
            return self._end("NEEDS_REVIEW", LINES["handover"], "Call went on too long")
        if intent == "human":
            return self._end("NEEDS_REVIEW", LINES["handover"], f"Asked for a person / complaint: {text}")

        # Waiting for a cancellation reason: whatever they say is the reason
        if self.state == "ASK_CANCEL_REASON":
            if intent == "confirm":                               # changed their mind
                return self._end("CONFIRMED", LINES["confirmed"])
            self.cancel_reason = u["cancel_reason"] or ("" if intent == "end_call" else text)
            return self._end("CANCELLED", LINES["cancelled"])

        if intent == "end_call":
            return self._end("NOT_CONFIRMED", LINES["not_confirmed"])
        if intent == "question":
            return self._reprompt()
        if intent == "cancel":
            if u["cancel_reason"]:
                self.cancel_reason = u["cancel_reason"]
                return self._end("CANCELLED", LINES["cancelled"])
            self.state = "ASK_CANCEL_REASON"
            return LINES["ask_reason"]

        if self.state == "ASK_CONFIRM":
            if intent == "confirm":
                return self._end("CONFIRMED", LINES["confirmed"])
            if intent == "change_address":
                return self._start_address_change(u["new_address"])
            if intent == "deny":
                return LINES["clarify_deny"]

        elif self.state == "ASK_NEW_ADDRESS":
            if u["new_address"]:
                return self._start_address_change(u["new_address"])

        elif self.state == "READ_BACK":
            if intent == "confirm":
                return self._end("ADDRESS_UPDATED", LINES["address_updated"])
            if intent == "change_address" and u["new_address"]:
                return self._start_address_change(u["new_address"])
            if intent in ("deny", "change_address"):
                return self._start_address_change("")

        self.unclear_count += 1
        if self.unclear_count >= MAX_UNCLEAR:
            return self._end("NEEDS_REVIEW", LINES["handover"], "Agent could not understand the customer")
        return LINES["unclear"] + " " + self._reprompt()

    # ---------- public API ----------
    def start(self):
        o = self.order
        line = LINES["greeting"].format(
            name=o["customer_name"], items=o["items"], amount=f"{o['amount']:,}",
            address=o["address"], city=o["city"],
        )
        self._log("agent", line)
        return line

    def handle(self, text):
        if self.ended:
            raise RuntimeError("This call has already ended")
        self.customer_turns += 1

        u, llm_ms = self._understand(text)
        intent = u["intent"]
        self._log("customer", text, intent=intent, llm_ms=llm_ms)

        reply_parts, retrieved, ans_ms = [], None, 0
        question = u["question"] or (text if intent == "question" else "")
        if question and intent in ("question", "confirm", "cancel"):
            answer, retrieved, ans_ms = self._answer(question)
            llm_ms += ans_ms
            if answer:
                reply_parts.append(answer)
            else:
                reply_parts.append(LINES["cant_answer"])
                self.review_reasons.append(f"Unanswered question: {question}")

        reply_parts.append(self._decide(intent, u, text))
        reply = " ".join(reply_parts)
        self._log("agent", reply, retrieved=retrieved, llm_ms=ans_ms or None)
        return {"reply": reply, "intent": intent, "llm_ms": llm_ms,
                "ended": self.ended, "outcome": self.outcome}