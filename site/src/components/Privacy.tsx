import { leaves } from "../content";
import "./Split.css";

export function Privacy() {
  return (
    <section className="split private" aria-labelledby="private-title">
      <h2 id="private-title">What leaves your device</h2>
      <div>
        <ul>
          {leaves.map((item) => (
            <li key={item.lead}>
              <strong>{item.lead}</strong> {item.rest}
            </li>
          ))}
        </ul>
        <p className="claim">
          Keys and the conversation stay on the device the app runs on. No analytics, no account. The page asks
          for a PIN and locks out repeated wrong guesses.
        </p>
      </div>
    </section>
  );
}
