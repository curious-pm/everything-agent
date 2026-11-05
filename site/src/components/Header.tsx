import { REPO } from "../content";
import { ReachyMark } from "./ReachyMark";
import "./Header.css";

export function Header() {
  return (
    <header className="bar">
      <a className="brand" href="#top" aria-label="Everything Agent, back to top">
        <ReachyMark />
        Everything Agent
      </a>
      <nav aria-label="Page">
        <a href="#how">How it works</a>
        <a href="#install">Install</a>
        <a href={REPO}>GitHub</a>
      </nav>
    </header>
  );
}
