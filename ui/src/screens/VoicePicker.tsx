import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Voice } from "../api/types";
import { Row } from "../components/controls";

const PAGE = 40;
const GENDERS: [string, string][] = [
  ["", "Any voice"],
  ["feminine", "Female"],
  ["masculine", "Male"],
  ["gender_neutral", "Neutral"],
];

const LANGUAGE_NAMES = new Intl.DisplayNames(["en"], { type: "language" });

function languageName(code: string): string {
  try {
    return LANGUAGE_NAMES.of(code) ?? code;
  } catch {
    return code;
  }
}

function describe(voice: Voice): string {
  const gender = GENDERS.find(([g]) => g === voice.gender)?.[1];
  return [voice.language && languageName(voice.language), gender].filter(Boolean).join(", ");
}

export function VoicePicker({ language }: { language: string }) {
  const [current, setCurrent] = useState<Voice | null>(null);
  const [library, setLibrary] = useState<Voice[] | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [lang, setLang] = useState(language && language !== "auto" ? language : "en");
  const [gender, setGender] = useState("");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [playing, setPlaying] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    api.voices().then((r) => {
      setCurrent(r.current);
      setLibrary(r.voices);
    }, (e: Error) => setError(e.message));
    return () => audio.current?.pause();
  }, []);

  const languages = useMemo(
    () => [...new Set((library ?? []).map((v) => v.language).filter(Boolean))]
      .sort((a, b) => languageName(a).localeCompare(languageName(b))),
    [library],
  );

  const matches = useMemo(() => {
    const words = query.trim().toLowerCase();
    return (library ?? []).filter((v) =>
      (!lang || v.language === lang)
      && (!gender || v.gender === gender)
      && (!words || `${v.name} ${v.description}`.toLowerCase().includes(words)));
  }, [library, lang, gender, query]);

  const play = async (voice: Voice) => {
    audio.current?.pause();
    setPlaying(voice.id);
    setNote("");
    try {
      const url = URL.createObjectURL(await api.voiceSample(voice.id, voice.language));
      const player = new Audio(url);
      audio.current = player;
      player.onended = () => {
        URL.revokeObjectURL(url);
        setPlaying((p) => (p === voice.id ? null : p));
      };
      await player.play();
    } catch (e) {
      setPlaying(null);
      setNote((e as Error).message);
    }
  };

  const choose = async (voice: Voice) => {
    setNote("");
    try {
      await api.useVoice(voice.id);
      setCurrent(voice);
      setNote(`Reachy now speaks as ${voice.name}.`);
    } catch (e) {
      setNote((e as Error).message);
    }
  };

  return (
    <>
      <Row label="Voice" hint={current ? [current.name, describe(current)].filter(Boolean).join(" · ") : error || "Loading…"}>
        <button className="btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Done" : "Change voice"}
        </button>
      </Row>
      {note && <p className="muted voice-note" role="status">{note}</p>}
      {open && !library && <p className="muted voice-note" role="status">{error || "Loading voices…"}</p>}
      {open && library && (
        <div className="voice-picker">
          <div className="voice-filters">
            <select className="field" aria-label="Language" value={lang} onChange={(e) => { setLang(e.target.value); setShown(PAGE); }}>
              <option value="">All languages</option>
              {languages.map((code) => <option key={code} value={code}>{languageName(code)}</option>)}
            </select>
            <select className="field" aria-label="Kind of voice" value={gender} onChange={(e) => { setGender(e.target.value); setShown(PAGE); }}>
              {GENDERS.map(([g, label]) => <option key={g} value={g}>{label}</option>)}
            </select>
            <input
              className="field"
              type="search"
              aria-label="Search voices"
              placeholder="Search, e.g. calm, warm, narrator"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }}
            />
          </div>
          <p className="muted voice-count">{matches.length} voices</p>
          <ul className="voice-list">
            {matches.slice(0, shown).map((v) => {
              const inUse = v.id === current?.id;
              return (
                <li key={v.id} className={inUse ? "in-use" : undefined}>
                  <span className="row-text">
                    <span>{v.name}</span>
                    <span className="row-hint">{v.description || describe(v)}</span>
                  </span>
                  <button className="btn" onClick={() => play(v)} disabled={playing === v.id} aria-label={`Hear ${v.name}`}>
                    {playing === v.id ? "Playing…" : "Hear"}
                  </button>
                  <button className="btn primary" onClick={() => choose(v)} disabled={inUse}>
                    {inUse ? "In use" : "Use"}
                  </button>
                </li>
              );
            })}
          </ul>
          {matches.length > shown && (
            <button className="btn" onClick={() => setShown(shown + PAGE)}>Show more voices</button>
          )}
        </div>
      )}
    </>
  );
}
