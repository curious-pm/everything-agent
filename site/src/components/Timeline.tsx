import { useEffect, useRef, useState } from "react";
import { timeline } from "../content";
import "./Timeline.css";

const MARKS = [0, 0.55, 2.25];
const END = 2.75;

function prefersStill(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function Timeline() {
  const section = useRef<HTMLElement>(null);
  const [clock, setClock] = useState<number | null>(() => (prefersStill() ? END : null));

  useEffect(() => {
    const node = section.current;
    if (clock !== null || !node || typeof IntersectionObserver === "undefined") return;
    let frame = 0;
    const watcher = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      watcher.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const seconds = Math.min(END, (now - start) / 1000);
        setClock(seconds);
        if (seconds < END) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    watcher.observe(node);
    return () => {
      watcher.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [clock]);

  const shown = clock ?? 0;
  return (
    <section ref={section} className="how" id="how" aria-labelledby="how-title">
      <h2 id="how-title">What happens after you stop talking</h2>
      <p className="intro">
        Everything streams, so Reachy starts its answer after the first sentence instead of the whole reply.
        Typical timings on a home connection:
      </p>
      <ol className="timeline">
        {timeline.map((step, i) => (
          <li key={step.title} data-phase={step.phase} className={shown >= MARKS[i] && clock !== null ? "reached" : ""}>
            <span className="when">{step.when}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </li>
        ))}
      </ol>
      <div className="track" aria-hidden="true">
        <div className="bar-chart">
          {(["listening", "thinking", "speaking"] as const).map((phase, i) => {
            const from = MARKS[i];
            const to = MARKS[i + 1] ?? END;
            const fill = Math.max(0, Math.min(1, (shown - from) / (to - from)));
            return (
              <span key={phase} className="seg" data-phase={phase} style={{ flexGrow: to - from }}>
                <span className="fill" style={{ transform: `scaleX(${fill})` }} />
              </span>
            );
          })}
        </div>
        <span className="clock">{shown.toFixed(1)} s</span>
      </div>
      <p className="note">
        Every reply logs a <code>Timing:</code> line, so you can measure it on your own setup. A faster model
        provider shortens the middle part.
      </p>
    </section>
  );
}
