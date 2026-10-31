import { SCREENS, useNav } from "../nav";
import { Icon } from "./Icon";
import { ReachyMark } from "./ReachyMark";
import "./Rail.css";

export function Rail() {
  const { screen, go } = useNav();
  return (
    <nav className="rail" aria-label="Main">
      <ReachyMark size={34} />
      {SCREENS.map((s) => (
        <button
          key={s.id}
          className={`rail-item${s.id === screen ? " on" : ""}`}
          aria-label={s.label}
          title={s.label}
          aria-current={s.id === screen ? "page" : undefined}
          onClick={() => go(s.id)}
        >
          <Icon name={s.icon} />
        </button>
      ))}
    </nav>
  );
}
