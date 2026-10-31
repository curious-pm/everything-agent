import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeviceInfo, SettingField } from "../api/types";
import { ReachyMark } from "../components/ReachyMark";
import { launcher } from "../host";
import "./Setup.css";

type Step = "hello" | "devices" | "keys" | "done";

const LINES: Record<Step, string> = {
  hello: "Hi, I'm Reachy.",
  devices: "Which microphone and speaker should I use?",
  keys: "Now give me a voice and a brain.",
  done: "All set.",
};

const OPENROUTER = "https://openrouter.ai/api/v1";

export function Setup() {
  const [fields, setFields] = useState<Record<string, SettingField>>({});
  const [devices, setDevices] = useState<DeviceInfo | null>(null);
  const [step, setStep] = useState<Step>("hello");
  const [values, setValues] = useState<Record<string, string>>({ CARTESIA_API_KEY: "", LLM_API_KEY: "" });
  const [choice, setChoice] = useState({ input: "", output: "" });
  const [otherModel, setOtherModel] = useState(false);
  const [autostart, setAutostart] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.settings().then((r) => {
      const byKey = Object.fromEntries(r.fields.map((f) => [f.key, f]));
      const baseUrl = byKey.LLM_BASE_URL?.value ?? OPENROUTER;
      setFields(byKey);
      setValues((v) => ({ ...v, LLM_BASE_URL: baseUrl, LLM_MODEL: byKey.LLM_MODEL?.value ?? "" }));
      setOtherModel(baseUrl !== OPENROUTER);
    }, (e: Error) => setError(e.message));
    api.devices().then((d) => {
      setDevices(d);
      setChoice(d.selected);
    }, () => setDevices(null));
    launcher.getAutostart().then(setAutostart, () => setAutostart(null));
  }, []);

  const steps: Step[] = devices?.can_choose ? ["hello", "devices", "keys", "done"] : ["hello", "keys", "done"];
  const index = steps.indexOf(step);
  const has = (key: string) => Boolean(fields[key]?.is_set || values[key]?.trim());
  const ollama = values.LLM_BASE_URL?.includes(":11434");
  const keysReady = has("CARTESIA_API_KEY") && (ollama || has("LLM_API_KEY"));
  const set = (key: string, value: string) => setValues({ ...values, [key]: value });

  const finish = async () => {
    setSaving(true);
    setError("");
    try {
      if (autostart !== null) await launcher.setAutostart(autostart);
      await api.saveSettings(values);
      const changed = devices && (choice.input !== devices.selected.input || choice.output !== devices.selected.output);
      if (changed) await api.saveDevices(choice);
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  };

  return (
    <main className="first-run">
      <div className="first-run-inner">
        <div className="first-run-top">
          <ReachyMark size={56} />
          <span className="muted">Step {index + 1} of {steps.length}</span>
        </div>
        <p className="voice first-run-line">{LINES[step]}</p>

        {step === "hello" && (
          <p className="first-run-text">
            I'm a little robot you can talk to. Setting me up takes about two minutes: I need one key to hear and speak,
            and one for the AI that does my thinking.
          </p>
        )}

        {step === "devices" && devices && (
          <div className="first-run-fields">
            <label>Microphone
              <select className="field" value={choice.input} onChange={(e) => setChoice({ ...choice, input: e.target.value })}>
                <option value="">System default</option>
                {devices.inputs.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <label>Speaker
              <select className="field" value={choice.output} onChange={(e) => setChoice({ ...choice, output: e.target.value })}>
                <option value="">System default</option>
                {devices.outputs.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <p className="muted">With the robot plugged in, I use its own microphone and speaker instead.</p>
          </div>
        )}

        {step === "keys" && (
          <div className="first-run-fields">
            <p className="first-run-text">Paste a key for each. They stay on this device.</p>
            <label>Key for hearing and speaking (Cartesia)
              <input
                className="field" type="password" autoComplete="off" value={values.CARTESIA_API_KEY}
                placeholder={fields.CARTESIA_API_KEY?.is_set ? "Saved; leave blank to keep" : "Paste your key"}
                onChange={(e) => set("CARTESIA_API_KEY", e.target.value)}
              />
            </label>
            <a href="https://play.cartesia.ai/keys" target="_blank" rel="noreferrer">Get a Cartesia key</a>
            <label>Key for thinking {otherModel ? "(your AI provider)" : "(OpenRouter)"}
              <input
                className="field" type="password" autoComplete="off" value={values.LLM_API_KEY}
                placeholder={fields.LLM_API_KEY?.is_set ? "Saved; leave blank to keep" : ollama ? "Not needed for Ollama" : "Paste your key"}
                onChange={(e) => set("LLM_API_KEY", e.target.value)}
              />
            </label>
            {!otherModel && <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">Get an OpenRouter key</a>}
            <label className="option">
              <input type="checkbox" checked={otherModel} onChange={(e) => {
                setOtherModel(e.target.checked);
                if (!e.target.checked) setValues({ ...values, LLM_BASE_URL: OPENROUTER, LLM_MODEL: fields.LLM_MODEL?.default ?? "" });
              }} />
              <span>Use another AI provider (any OpenAI-compatible one, or Ollama)</span>
            </label>
            {otherModel && (
              <>
                <label>AI model address
                  <input className="field" value={values.LLM_BASE_URL} placeholder="https://…/v1" onChange={(e) => set("LLM_BASE_URL", e.target.value)} />
                </label>
                <label>AI model
                  <input className="field" value={values.LLM_MODEL} onChange={(e) => set("LLM_MODEL", e.target.value)} />
                </label>
              </>
            )}
          </div>
        )}

        {step === "done" && (
          <div className="first-run-fields">
            <p className="first-run-text">Once you press Start, just talk to me. Try “What can you do?”</p>
            {autostart !== null && (
              <label className="option">
                <input type="checkbox" checked={autostart} onChange={(e) => setAutostart(e.target.checked)} />
                <span>Start Reachy when I log in</span>
              </label>
            )}
          </div>
        )}

        {error && <p className="page-error" role="alert">{error}</p>}
        <div className="first-run-actions">
          {index > 0 ? <button className="btn" onClick={() => setStep(steps[index - 1])} disabled={saving}>Back</button> : <span />}
          {step === "done" ? (
            <button className="btn primary" onClick={finish} disabled={saving || !keysReady}>{saving ? "Starting…" : "Start Reachy"}</button>
          ) : (
            <button className="btn primary" onClick={() => setStep(steps[index + 1])} disabled={step === "keys" && !keysReady}>
              {step === "hello" ? "Set up Reachy" : "Continue"}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
