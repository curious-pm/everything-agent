import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api/client";
import { applyMessage, useLive, type LiveData } from "./api/live";
import { SignIn } from "./App";
import { Home } from "./screens/Home";
import { Setup } from "./screens/Setup";
import { caption } from "./wording";

const empty: LiveData = { connection: "live", state: {}, levels: { mic: 0, speaker: 0 }, lines: [], notice: "" };

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("live messages", () => {
  it("replaces state and levels", () => {
    expect(applyMessage(empty, { type: "state", phase: "thinking", mic_muted: true })).toEqual({
      state: { phase: "thinking", mic_muted: true },
    });
    expect(applyMessage(empty, { type: "levels", mic: 0.2, speaker: 0.1 })).toEqual({ levels: { mic: 0.2, speaker: 0.1 } });
  });

  it("appends transcript lines and ignores unknown events", () => {
    const next = applyMessage(empty, { type: "event", seq: 1, at: 0, kind: "transcript", role: "user", text: "hi" });
    expect(next.lines).toEqual([{ role: "user", text: "hi" }]);
    expect(applyMessage(empty, { type: "event", seq: 2, at: 0, kind: "barge_in" })).toEqual({});
  });

  it("shows a problem until the user speaks again, and clears the conversation", () => {
    const withNotice = { ...empty, ...applyMessage(empty, { type: "event", seq: 3, at: 0, kind: "problem", text: "No key" }) };
    expect(withNotice.notice).toBe("No key");
    expect(applyMessage(withNotice, { type: "event", seq: 4, at: 0, kind: "transcript", role: "user", text: "again" }).notice).toBe("");
    const withLines = { ...empty, lines: [{ role: "user" as const, text: "x" }] };
    expect(applyMessage(withLines, { type: "event", seq: 5, at: 0, kind: "cleared" })).toEqual({ lines: [] });
  });
});

describe("withdrawn lines", () => {
  it("drop the line the user went on to finish", () => {
    const data = { ...empty, lines: [{ role: "user" as const, text: "Nice." }] };
    expect(applyMessage(data, { type: "event", seq: 6, at: 0, kind: "withdrawn", text: "Nice." })).toEqual({ lines: [] });
    expect(applyMessage(data, { type: "event", seq: 7, at: 0, kind: "withdrawn", text: "Other" })).toEqual({});
  });
});

describe("captions", () => {
  const lines = [
    { role: "user" as const, text: "What's the capital of France?" },
    { role: "assistant" as const, text: "Paris." },
  ];
  it("shows what Reachy says while speaking", () => {
    expect(caption({ phase: "speaking" }, lines)).toBe("Paris.");
  });
  it("says it can't hear when the mic is muted", () => {
    expect(caption({ phase: "listening", mic_muted: true }, lines)).toBe("I can't hear you right now.");
  });
  it("says how to wake it", () => {
    expect(caption({ phase: "asleep" }, lines)).toMatch(/wake me up/i);
  });
});

describe("Home", () => {
  beforeEach(() => useLive.setState({ ...empty, state: { phase: "asleep", mic_muted: true } }));

  it("offers to wake Reachy and labels the muted mic", () => {
    render(<Home />);
    expect(screen.getByRole("button", { name: /wake up/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Turn Reachy's microphone on" })).toBeInTheDocument();
  });

  it("sends typed messages from the conversation drawer", async () => {
    const say = vi.spyOn(api, "say").mockResolvedValue({});
    render(<Home />);
    fireEvent.click(screen.getByRole("button", { name: /conversation/i }));
    fireEvent.change(screen.getByPlaceholderText("Type to Reachy"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(say).toHaveBeenCalledWith("hello"));
  });
});

describe("Sign in", () => {
  it("asks for a new PIN twice the first time", async () => {
    vi.spyOn(api, "auth").mockResolvedValue({ signed_in: false, pin_set: false });
    const setPin = vi.spyOn(api, "setPin").mockResolvedValue({});
    const done = vi.fn();
    render(<SignIn onDone={done} />);
    fireEvent.change(await screen.findByPlaceholderText("PIN"), { target: { value: "246810" } });
    fireEvent.change(screen.getByPlaceholderText("PIN again"), { target: { value: "246811" } });
    fireEvent.click(screen.getByRole("button", { name: "Set PIN" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("don't match");
    fireEvent.change(screen.getByPlaceholderText("PIN"), { target: { value: "246810" } });
    fireEvent.change(screen.getByPlaceholderText("PIN again"), { target: { value: "246810" } });
    fireEvent.click(screen.getByRole("button", { name: "Set PIN" }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(setPin).toHaveBeenCalledWith("246810");
  });

  it("goes straight through when already signed in", async () => {
    vi.spyOn(api, "auth").mockResolvedValue({ signed_in: true, pin_set: true });
    const done = vi.fn();
    render(<SignIn onDone={done} />);
    await waitFor(() => expect(done).toHaveBeenCalled());
  });
});

describe("Setup", () => {
  const field = (key: string, kind: string, value = "", is_set = false) =>
    ({ key, label: key, kind, hint: "", required: false, is_set, value, default: value });

  it("won't go past the keys until both are there, then saves them", async () => {
    vi.spyOn(api, "settings").mockResolvedValue({
      fields: [
        field("CARTESIA_API_KEY", "secret", "••••1234", true) as never,
        field("LLM_API_KEY", "secret") as never,
        field("LLM_BASE_URL", "text", "https://openrouter.ai/api/v1") as never,
        field("LLM_MODEL", "text", "google/gemini-2.5-flash") as never,
      ],
      missing: ["LLM_API_KEY"],
    });
    vi.spyOn(api, "devices").mockResolvedValue({ inputs: [], outputs: [], selected: { input: "", output: "" }, can_choose: false, error: "" });
    const save = vi.spyOn(api, "saveSettings").mockResolvedValue({ saved: [] });
    render(<Setup />);
    fireEvent.click(await screen.findByRole("button", { name: "Set up Reachy" }));
    const next = screen.getByRole("button", { name: "Continue" });
    await waitFor(() => expect(next).toBeDisabled());
    fireEvent.change(screen.getByPlaceholderText("Paste your key"), { target: { value: "sk-or-1" } });
    expect(next).toBeEnabled();
    fireEvent.click(next);
    fireEvent.click(screen.getByRole("button", { name: "Start Reachy" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0][0]).toMatchObject({ LLM_API_KEY: "sk-or-1", CARTESIA_API_KEY: "", LLM_BASE_URL: "https://openrouter.ai/api/v1" });
  });
});
