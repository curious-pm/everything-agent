import { REPO } from "../content";
import "./Split.css";

export function OpenSource() {
  return (
    <section className="split open" aria-labelledby="open-title">
      <h2 id="open-title">Built in the open, one tool at a time</h2>
      <div>
        <p>
          Everything Agent does one thing, conversation, and does it well. New abilities arrive as tools the
          model can use: a tool returns a result, or works in the background and speaks when it's done, the
          way <code>ask_claude</code> does. Ideas on the list, not built yet: reminders, routines and a memory
          that tidies itself.
        </p>
        <div className="actions">
          <a className="btn primary" href={REPO}>See the code on GitHub</a>
          <a className="btn" href={`${REPO}/blob/main/CONTRIBUTING.md`}>Read how to contribute</a>
        </div>
      </div>
    </section>
  );
}
