import { REPO } from "../content";
import "./Footer.css";

export function Footer() {
  return (
    <footer className="foot">
      <p>
        Apache-2.0. Everything Agent is an independent project, not affiliated with or endorsed by Pollen
        Robotics, Hugging Face or Anthropic. Reachy Mini is a robot by Pollen Robotics and Hugging Face; this
        app is built on its open-source SDK. Claude is a trademark of Anthropic, PBC.
      </p>
      <p>
        <a href={`${REPO}/blob/main/SECURITY.md`}>Report a security problem</a>
      </p>
    </footer>
  );
}
