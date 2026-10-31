import { create } from "zustand";
import { apiToken, wsUrl } from "../host";
import { api } from "./client";
import type { Line, LiveState, ServerMessage } from "./types";

export type Connection = "connecting" | "live" | "offline" | "login";

const MAX_LINES = 200;
const RETRY_MS = [1000, 2000, 5000];
const CLOSE_UNAUTHORIZED = 4401;

export type LiveData = {
  connection: Connection;
  state: LiveState;
  levels: { mic: number; speaker: number };
  lines: Line[];
  notice: string;
};

export function applyMessage(data: LiveData, msg: ServerMessage): Partial<LiveData> {
  if (msg.type === "state") {
    const { type: _type, ...state } = msg;
    return { state };
  }
  if (msg.type === "levels") return { levels: { mic: msg.mic, speaker: msg.speaker } };
  if (msg.kind === "transcript" && (msg.role === "user" || msg.role === "assistant") && typeof msg.text === "string") {
    const line: Line = { role: msg.role, text: msg.text };
    return { lines: [...data.lines, line].slice(-MAX_LINES), notice: msg.role === "user" ? "" : data.notice };
  }
  if (msg.kind === "withdrawn" && typeof msg.text === "string") {
    const last = data.lines.at(-1);
    return last?.role === "user" && last.text === msg.text ? { lines: data.lines.slice(0, -1) } : {};
  }
  if (msg.kind === "problem" && typeof msg.text === "string") return { notice: msg.text };
  if (msg.kind === "cleared") return { lines: [] };
  return {};
}

type LiveStore = LiveData & { connect: () => void; disconnect: () => void };

let socket: WebSocket | null = null;
let retryTimer: number | undefined;
let attempt = 0;

export const useLive = create<LiveStore>((set, get) => ({
  connection: "connecting",
  state: {},
  levels: { mic: 0, speaker: 0 },
  lines: [],
  notice: "",

  connect() {
    window.clearTimeout(retryTimer);
    socket?.close();
    set({ connection: "connecting" });
    const ws = new WebSocket(wsUrl("/api/events"));
    socket = ws;
    ws.onopen = () => {
      const token = apiToken();
      if (token) ws.send(JSON.stringify({ token }));
    };
    ws.onmessage = (ev) => {
      let msg: ServerMessage;
      try {
        msg = JSON.parse(ev.data) as ServerMessage;
      } catch {
        return;
      }
      if (get().connection !== "live") {
        attempt = 0;
        set({ connection: "live" });
        void api.conversation().then((c) => set({ lines: c.messages })).catch(() => {});
      }
      set(applyMessage(get(), msg));
    };
    ws.onclose = (ev) => {
      if (socket !== ws) return;
      socket = null;
      if (ev.code === CLOSE_UNAUTHORIZED) {
        set({ connection: "login" });
        return;
      }
      set({ connection: "offline" });
      retryTimer = window.setTimeout(() => get().connect(), RETRY_MS[Math.min(attempt++, RETRY_MS.length - 1)]);
    };
  },

  disconnect() {
    window.clearTimeout(retryTimer);
    const ws = socket;
    socket = null;
    ws?.close();
  },
}));
