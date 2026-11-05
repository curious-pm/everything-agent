import { useDownload } from "../useRelease";
import { Stage } from "./Stage";
import "./Hero.css";

export function Hero() {
  const download = useDownload();
  return (
    <section className="hero" id="top">
      <div className="pitch">
        <h1>Talk with your Reachy&nbsp;Mini the way you'd talk with a person.</h1>
        <p className="lede">
          No wake word, no button. Everything Agent listens, answers out loud, moves Reachy's head while it
          speaks, and stops when you talk over it. Open source, on the robot, your laptop or any browser.
        </p>
        <div className="actions">
          <a className="btn primary" href="#install">Install on Reachy Mini</a>
          <a className="btn" href={download.href}>{download.label}</a>
        </div>
        <p className="fine">
          {download.version ? `${download.version}, ` : ""}Apache-2.0. Works without a robot too, through your
          computer's microphone and speaker.
        </p>
      </div>
      <Stage />
    </section>
  );
}
