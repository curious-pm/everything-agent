import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { create } from "zustand";

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
    __EVERYTHING_AGENT__?: { apiBase: string; token: string; daemonBase?: string };
  }
}

const DAEMON_PORT = 8000;

export function isTauri(): boolean {
  return Boolean(window.__TAURI_INTERNALS__);
}

export type CoreState = { state: string; label: string; detail: string };

export const useCore = create<{ core: CoreState | null }>(() => ({ core: null }));

if (isTauri()) {
  void invoke<CoreState>("core_state").then((core) => useCore.setState({ core }));
  void listen<CoreState>("core-state", (event) => useCore.setState({ core: event.payload }));
}

export function apiBase(): string {
  return window.__EVERYTHING_AGENT__?.apiBase ?? "";
}

export function apiToken(): string | null {
  return window.__EVERYTHING_AGENT__?.token ?? null;
}

function toWs(url: string): string {
  return url.replace(/^http/, "ws");
}

export function wsUrl(path: string): string {
  return toWs(apiBase() || window.location.origin) + path;
}

export function daemonWsUrl(path: string): string {
  const { protocol, hostname } = window.location;
  return toWs(window.__EVERYTHING_AGENT__?.daemonBase ?? `${protocol}//${hostname || "127.0.0.1"}:${DAEMON_PORT}`) + path;
}

export const launcher = {
  getAutostart: async (): Promise<boolean | null> => (isTauri() ? invoke<boolean>("get_autostart") : null),
  setAutostart: async (enabled: boolean): Promise<boolean | null> =>
    isTauri() ? invoke<boolean>("set_autostart", { enabled }) : null,
};
