import { useState } from "react";
import home from "../../../docs/screenshot-home.png";
import settings from "../../../docs/screenshot-settings.png";
import "./AppTour.css";

const views = [
  {
    id: "home",
    label: "Home",
    src: home,
    alt: "The app's home screen: Reachy in 3D, with the conversation open beside it",
    caption: "Reachy in 3D, moving as the real robot moves, with the conversation beside it. Mute, sleep, or type instead of talking.",
  },
  {
    id: "settings",
    label: "Settings",
    src: settings,
    alt: "The app's settings: language, voice and Reachy's personality",
    caption: "Pick a voice, the language Reachy replies in, and how it behaves. Keys and models live under Advanced.",
  },
];

export function AppTour() {
  const [active, setActive] = useState(views[0].id);
  const view = views.find((v) => v.id === active) ?? views[0];
  return (
    <section className="tour" aria-labelledby="tour-title">
      <h2 id="tour-title">The same app on the robot, your desktop and your phone</h2>
      <div className="switch" role="group" aria-label="Screen to show">
        {views.map((v) => (
          <button key={v.id} type="button" aria-pressed={v.id === active} onClick={() => setActive(v.id)}>
            {v.label}
          </button>
        ))}
      </div>
      <figure className="window">
        <div className="window-bar" aria-hidden="true">
          <span />
          <span />
          <span />
          <span className="window-title">Everything Agent</span>
        </div>
        <div className="window-body">
          {views.map((v) => (
            <img
              key={v.id}
              src={v.src}
              alt={v.alt}
              width={1920}
              height={1200}
              loading="lazy"
              className={v.id === active ? "shown" : ""}
              aria-hidden={v.id !== active}
            />
          ))}
        </div>
        <figcaption>{view.caption}</figcaption>
      </figure>
    </section>
  );
}
