import { apiBase, apiToken } from "../host";
import type { Check, DeviceInfo, Info, Line, SettingField, Voice } from "./types";

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = apiToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${apiBase()}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!response.ok) {
    const detail = await response.json().then((b) => b?.detail, () => undefined);
    const message = Array.isArray(detail) ? detail.map((d) => d?.msg).filter(Boolean).join(" ") : detail;
    throw new Error(String(message || response.statusText));
  }
  return response;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  return (await send(method, path, body)).json() as Promise<T>;
}

export const MIN_PIN_LENGTH = 6;

export const api = {
  auth: () => request<{ signed_in: boolean; pin_set: boolean }>("GET", "/api/auth"),
  login: (pin: string) => request("POST", "/api/auth/login", { pin }),
  setPin: (pin: string, current = "") => request("POST", "/api/auth/pin", current ? { pin, current } : { pin }),
  info: () => request<Info>("GET", "/api/info"),
  say: (text: string) => request("POST", "/api/say", { text }),
  mute: (change: { mic?: boolean; speaker?: boolean }) => request<{ mic: boolean; speaker: boolean }>("POST", "/api/mute", change),
  sleep: () => request("POST", "/api/sleep"),
  wake: () => request("POST", "/api/wake"),
  conversation: (limit = 60) => request<{ messages: Line[] }>("GET", `/api/conversation?limit=${limit}`),
  clearConversation: () => request("DELETE", "/api/conversation"),
  settings: () => request<{ fields: SettingField[]; missing: string[] }>("GET", "/api/settings"),
  saveSettings: (values: Record<string, string>) => request<{ saved: string[] }>("POST", "/api/settings", { values }),
  voices: () => request<{ current: Voice; voices: Voice[] }>("GET", "/api/voices"),
  voiceSample: async (id: string, language: string) => (await send("POST", "/api/voices/sample", { id, language })).blob(),
  useVoice: (id: string) => request<{ saved: boolean }>("POST", "/api/voices/use", { id }),
  checks: () => request<{ checks: Record<string, Check> }>("GET", "/api/checks"),
  logs: (name: string) => request<{ name: string; text: string }>("GET", `/api/logs?name=${encodeURIComponent(name)}&lines=400`),
  openLogs: () => request("POST", "/api/logs/open"),
  devices: () => request<DeviceInfo>("GET", "/api/devices"),
  saveDevices: (choice: { input: string; output: string }) => request("POST", "/api/devices", choice),
};
