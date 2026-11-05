import { exchanges } from "../content";
import "./Exchanges.css";

export function Exchanges() {
  return (
    <section className="does" aria-labelledby="does-title">
      <h2 id="does-title">What it does</h2>
      <dl className="exchanges">
        {exchanges.map((item) => (
          <div key={item.title}>
            <dt>{item.title}</dt>
            <dd>
              {item.you && <p className="you">{item.you}</p>}
              {item.reachy && <p className="reachy voice">{item.reachy}</p>}
              <p className="more">{item.more}</p>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
