import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, MIN_PIN_LENGTH } from "../api/client";
import type { Check, DeviceInfo, Info, SettingField } from "../api/types";
import { Notice, Row, SwitchRow } from "../components/controls";
import { isTauri, launcher } from "../host";
import { VoicePicker } from "./VoicePicker";
import "./Page.css";
import "./Settings.css";

type Section = "talk" | "listen" | "devices" | "advanced";

const LANGUAGES = [
  ["auto", "Reply in whatever language I speak"],
  ["en", "Always English"],
  ["hi", "Always Hindi"],
  ["fr", "Always French"],
  ["es", "Always Spanish"],
  ["ja", "Always Japanese"],
];

const SENSITIVITY = [
  ["0.015", "Very quiet room"],
  ["0.03", "Normal room"],
  ["0.05", "Noisy room"],
];

const SECTIONS: [Section, string][] = [
  ["talk", "How Reachy talks"],
  ["listen", "Listening"],
  ["devices", "Microphone and speaker"],
  ["advanced", "Advanced"],
];

type Fields = Record<string, SettingField>;

function useFields() {
  const [fields, setFields] = useState<Fields | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = useCallback(() => {
    api.settings().then((r) => setFields(Object.fromEntries(r.fields.map((f) => [f.key, f]))), (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const save = async (values: Record<string, string>, note = "Saved. Reachy uses it from now on."): Promise<boolean> => {
    setError("");
    setSaved("");
    try {
      await api.saveSettings(values);
      setSaved(note);
      load();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    }
  };
  const value = (key: string) => fields?.[key]?.value ?? "";
  const clearNotes = useCallback(() => {
    setSaved("");
    setError("");
  }, []);
  return { fields, save, value, error, saved, clearNotes };
}

type FieldsApi = ReturnType<typeof useFields>;

export function Settings() {
  const [section, setSection] = useState<Section>("talk");
  const [devices, setDevices] = useState<DeviceInfo | null>(null);
  const fields = useFields();
  useEffect(() => {
    api.devices().then(setDevices, () => setDevices(null));
  }, []);

  const sections = devices?.can_choose ? SECTIONS : SECTIONS.filter(([id]) => id !== "devices");

  return (
    <main className="settings">
      <nav className="settings-nav" aria-label="Settings sections">
        <h1>Settings</h1>
        {sections.map(([id, label]) => (
          <button key={id} aria-current={section === id ? "page" : undefined} onClick={() => {
            fields.clearNotes();
            setSection(id);
          }}>{label}</button>
        ))}
      </nav>
      <section className="settings-body page">
        {fields.error && <p className="page-error" role="alert">{fields.error}</p>}
        {fields.saved && <Notice>{fields.saved}</Notice>}
        {section === "talk" && <Talk fields={fields} />}
        {section === "listen" && <Listening fields={fields} />}
        {section === "devices" && devices && <Devices info={devices} />}
        {section === "advanced" && <Advanced fields={fields} />}
      </section>
    </main>
  );
}

function Talk({ fields }: { fields: FieldsApi }) {
  const [personality, setPersonality] = useState<string | null>(null);
  if (!fields.fields) return null;
  const current = personality ?? fields.value("SYSTEM_PROMPT");
  return (
    <>
      <h2 className="section-title">How Reachy talks</h2>
      <Row label="Language">
        <select className="field" value={fields.value("LANGUAGE_CODE") || "auto"} onChange={(e) => fields.save({ LANGUAGE_CODE: e.target.value })}>
          {LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
        </select>
      </Row>
      <VoicePicker key={fields.value("LANGUAGE_CODE") || "auto"} language={fields.value("LANGUAGE_CODE") || "auto"} />
      <div className="row-item stacked">
        <label className="row-text" htmlFor="personality">
          <span>Personality</span>
          <span className="row-hint">{fields.fields.SYSTEM_PROMPT?.hint}</span>
        </label>
        <textarea
          id="personality" className="field" rows={4} value={current}
          placeholder="You are Reachy Mini, a small, friendly desk robot…" onChange={(e) => setPersonality(e.target.value)}
        />
        <div className="form-actions">
          <button className="btn primary" disabled={personality === null} onClick={async () => {
            if (await fields.save({ SYSTEM_PROMPT: current })) setPersonality(null);
          }}>Save personality</button>
        </div>
      </div>
    </>
  );
}

function Listening({ fields }: { fields: FieldsApi }) {
  if (!fields.fields) return null;
  const sensitivity = fields.value("VAD_THRESHOLD") || "0.03";
  const options = SENSITIVITY.some(([v]) => v === sensitivity) ? SENSITIVITY : [...SENSITIVITY, [sensitivity, sensitivity]];
  return (
    <>
      <h2 className="section-title">Listening</h2>
      <Row label="My room is" hint={fields.fields.VAD_THRESHOLD?.hint}>
        <select className="field" value={sensitivity} onChange={(e) => fields.save({ VAD_THRESHOLD: e.target.value })}>
          {options.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </Row>
      <SwitchRow
        label={fields.fields.BARGE_IN_ENABLED?.label ?? "Stop talking when I interrupt"}
        hint={fields.fields.BARGE_IN_ENABLED?.hint}
        checked={fields.value("BARGE_IN_ENABLED") === "true"}
        onChange={(v) => fields.save({ BARGE_IN_ENABLED: v ? "true" : "false" })}
      />
    </>
  );
}

function Devices({ info }: { info: DeviceInfo }) {
  const [choice, setChoice] = useState(info.selected);
  const [note, setNote] = useState(info.error);

  const update = async (change: Partial<typeof choice>) => {
    const next = { ...choice, ...change };
    setChoice(next);
    try {
      await api.saveDevices(next);
      setNote("Saved. Reachy restarts to use it.");
    } catch (e) {
      setNote((e as Error).message);
    }
  };

  const select = (label: string, key: "input" | "output", options: string[]) => (
    <Row label={label}>
      <select className="field" value={choice[key]} onChange={(e) => update({ [key]: e.target.value })}>
        <option value="">System default</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
        {choice[key] && !options.includes(choice[key]) && <option value={choice[key]}>{choice[key]} (not connected)</option>}
      </select>
    </Row>
  );

  return (
    <>
      <h2 className="section-title">Microphone and speaker</h2>
      <p className="muted">Used when the robot isn't plugged in. With the robot, Reachy uses its own.</p>
      {note && <p className="muted" role="status">{note}</p>}
      {select("Microphone", "input", info.inputs)}
      {select("Speaker", "output", info.outputs)}
    </>
  );
}

const KEY_FIELDS = ["CARTESIA_API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"];

const CHECK_LABELS: Record<string, string> = {
  cartesia: "Hearing and speaking (Cartesia)",
  llm: "Thinking (AI model)",
  robot: "Robot",
  mic: "Microphone",
  claude: "Hard questions (Claude Code)",
};

function Advanced({ fields }: { fields: FieldsApi }) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [checks, setChecks] = useState<Record<string, Check> | null>(null);
  const [checking, setChecking] = useState(false);
  const [autostart, setAutostart] = useState<boolean | null>(null);
  const [info, setInfo] = useState<Info | null>(null);

  const runChecks = useCallback(async () => {
    setChecking(true);
    try {
      setChecks((await api.checks()).checks);
    } catch {
      setChecks(null);
    } finally {
      setChecking(false);
    }
  }, []);
  const recheckSoon = () => window.setTimeout(() => void runChecks(), 1500);

  useEffect(() => {
    void runChecks();
    api.info().then(setInfo, () => setInfo(null));
    launcher.getAutostart().then(setAutostart, () => setAutostart(null));
  }, [runChecks]);

  const all = fields.fields;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!(await fields.save(draft, "Saved. Reachy restarted its conversation with the new keys."))) return;
    setDraft({});
    recheckSoon();
  };

  return (
    <>
      <h2 className="section-title">Advanced</h2>
      <form className="keys-form" onSubmit={submit}>
        <h3>Keys and AI model</h3>
        {all && KEY_FIELDS.map((key) => {
          const f = all[key];
          if (!f) return null;
          const secret = f.kind === "secret";
          return (
            <Row key={key} label={f.label} hint={secret && f.is_set ? `${f.hint} Leave blank to keep the saved one.` : f.hint}>
              <input
                className="field" type={secret ? "password" : "text"} autoComplete="off" aria-label={f.label}
                value={draft[key] ?? (secret ? "" : f.value)}
                placeholder={secret ? (f.is_set ? `${f.value} (saved)` : "Paste your key") : f.default}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              />
            </Row>
          );
        })}
        <div className="form-actions">
          <button className="btn primary" type="submit" disabled={Object.keys(draft).length === 0}>Save keys</button>
        </div>
      </form>

      {all?.CLAUDE_CODE_ENABLED && (
        <SwitchRow
          label={all.CLAUDE_CODE_ENABLED.label}
          hint={all.CLAUDE_CODE_ENABLED.hint}
          checked={fields.value("CLAUDE_CODE_ENABLED") !== "false"}
          onChange={async (v) => {
            await fields.save({ CLAUDE_CODE_ENABLED: v ? "true" : "false" });
            recheckSoon();
          }}
        />
      )}

      <Row label="Check that everything works" hint={checking ? "Checking…" : undefined}>
        <button className="btn" onClick={runChecks} disabled={checking}>Check again</button>
      </Row>
      {checks && (
        <ul className="checks">
          {Object.entries(checks).map(([key, c]) => (
            <li key={key} className={`check ${c.status}`}>
              <span className="dot" aria-hidden="true" />
              <span className="row-text">
                <span>{CHECK_LABELS[key] ?? key}</span>
                <span className="row-hint">{c.detail}</span>
              </span>
              <span className="visually-hidden">{c.status === "ok" ? "working" : c.status === "fail" ? "not working" : "needs a look"}</span>
            </li>
          ))}
        </ul>
      )}

      <WebAccess info={info} />
      {autostart !== null && (
        <SwitchRow
          label="Start Reachy when I log in"
          checked={autostart}
          onChange={async (enabled) => {
            const now = await launcher.setAutostart(enabled).catch(() => null);
            if (now !== null) setAutostart(now);
          }}
        />
      )}
      {isTauri() ? (
        <Row label="Logs for troubleshooting">
          <button className="btn" onClick={() => api.openLogs().catch(() => {})}>Show logs folder</button>
        </Row>
      ) : (
        <Logs />
      )}
      {info && <p className="muted version">Everything Agent {info.version}</p>}
    </>
  );
}

function WebAccess({ info }: { info: Info | null }) {
  const [pin, setPin] = useState("");
  const [current, setCurrent] = useState("");
  const [note, setNote] = useState("");
  if (!info) return null;
  const needsCurrent = info.pin_set && !isTauri();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.setPin(pin, current);
      setPin("");
      setCurrent("");
      setNote(info.desktop && !info.lan ? "PIN saved. Restart Reachy to open the page to your network." : "PIN saved.");
    } catch (err) {
      setNote((err as Error).message);
    }
  };

  const where = info.lan ? `Open ${info.address} on any device on your network.` : "Set a PIN to open Reachy from your phone or another computer.";
  return (
    <form className="row-item" onSubmit={submit}>
      <span className="row-text">
        <span>{info.pin_set ? "Change the web page PIN" : "Web page PIN"}</span>
        <span className="row-hint">{note || where}</span>
      </span>
      <span className="row-control">
        {needsCurrent && (
          <input className="field" type="password" inputMode="numeric" aria-label="Current PIN" placeholder="Current PIN" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
        )}
        <input className="field" type="password" inputMode="numeric" aria-label="New PIN" placeholder="New PIN" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="new-password" />
        <button className="btn" type="submit" disabled={pin.length < MIN_PIN_LENGTH || (needsCurrent && !current)}>Save PIN</button>
      </span>
    </form>
  );
}

const LOGS: [string, string][] = [
  ["app", "Reachy"],
  ["daemon", "Robot"],
  ["desktop", "Desktop app"],
];

function Logs() {
  const [name, setName] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async (which: string) => {
    setName(which);
    setNote("Loading…");
    try {
      const r = await api.logs(which);
      setText(r.text);
      setNote(r.text ? "" : "Nothing logged yet.");
    } catch (e) {
      setText("");
      setNote((e as Error).message);
    }
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setNote("Copied.");
    } catch {
      setNote("Couldn't copy. Select the text and copy it instead.");
    }
  };

  return (
    <>
      <Row label="Logs for troubleshooting">
        {name === null ? (
          <button className="btn" onClick={() => load("app")}>Show logs</button>
        ) : (
          <>
            <select className="field" aria-label="Which log" value={name} onChange={(e) => load(e.target.value)}>
              {LOGS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
            <button className="btn" onClick={() => load(name)}>Refresh</button>
            <button className="btn" onClick={copy} disabled={!text}>Copy</button>
          </>
        )}
      </Row>
      {name !== null && (
        <>
          {note && <p className="muted" role="status">{note}</p>}
          {text && <pre className="log-text">{text}</pre>}
        </>
      )}
    </>
  );
}
