import { timeline } from "../content";
import "./Timeline.css";

export function Timeline() {
  return (
    <section className="how" id="how" aria-labelledby="how-title">
      <h2 id="how-title">What happens after you stop talking</h2>
      <p className="intro">
        Everything streams, so Reachy starts its answer after the first sentence instead of the whole reply.
        Typical timings on a home connection:
      </p>
      <ol className="timeline">
        {timeline.map((step) => (
          <li key={step.title} data-phase={step.phase}>
            <span className="when">{step.when}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </li>
        ))}
      </ol>
      <div className="bar-chart" aria-hidden="true">
        <span className="seg" data-phase="listening" />
        <span className="seg" data-phase="thinking" />
        <span className="seg" data-phase="speaking" />
      </div>
      <p className="note">
        Every reply logs a <code>Timing:</code> line, so you can measure it on your own setup. A faster model
        provider shortens the middle part.
      </p>
    </section>
  );
}
