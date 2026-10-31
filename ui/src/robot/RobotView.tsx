import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { useLive } from "../api/live";
import { RobotFigure } from "../components/RobotFigure";
import type { StreamStatus } from "./RobotScene";
import "./RobotView.css";

const RobotScene = lazy(() => import("./RobotScene"));

function webglAvailable(): boolean {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}

class FlatOnError extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <RobotFigure /> : this.props.children;
  }
}

function stateColor(): string {
  return getComputedStyle(document.documentElement).getPropertyValue("--state").trim() || "#3f7bff";
}

export function RobotView() {
  const phase = useLive((s) => s.state.phase);
  const speaker = useLive((s) => s.levels.speaker);
  const [color, setColor] = useState(stateColor);
  const [status, setStatus] = useState<StreamStatus>("loading");
  const [canRender] = useState(webglAvailable);

  useEffect(() => {
    const id = requestAnimationFrame(() => setColor(stateColor()));
    return () => cancelAnimationFrame(id);
  }, [phase]);

  if (!canRender) return <RobotFigure />;
  return (
    <div className="robot-view">
      <FlatOnError>
        <Suspense fallback={<RobotFigure />}>
          <RobotScene stateColor={color} speakerLevel={phase === "speaking" ? speaker : 0} onStatus={setStatus} />
        </Suspense>
      </FlatOnError>
      {status !== "live" && (
        <p className="robot-view-note muted">{status === "loading" ? "Finding Reachy…" : "Can't reach the robot right now."}</p>
      )}
    </div>
  );
}
