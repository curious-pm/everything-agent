import { useEffect, useRef, useState } from "react";
import type { Phase } from "../content";
import type { RobotController } from "../robot/scene";
import { Robot } from "./Robot";
import "./Robot3D.css";

const IDLE_MS = 3500;

function webglAvailable(): boolean {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}

function phaseColor(phase: Phase): string {
  const name = { listening: "--listen", thinking: "--think", speaking: "--speak" }[phase];
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#3f7bff";
}

export function Robot3D({ phase, still }: { phase: Phase; still: boolean }) {
  const holder = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const controller = useRef<RobotController | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!webglAvailable() || !canvas.current) return;
    let cancelled = false;
    import("../robot/scene")
      .then(({ mountRobot }) => mountRobot(canvas.current!, { still }))
      .then((robot) => {
        if (cancelled) {
          robot.dispose();
          return;
        }
        controller.current = robot;
        setReady(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      controller.current?.dispose();
      controller.current = null;
    };
  }, [still]);

  useEffect(() => {
    controller.current?.setMood(phase, phaseColor(phase));
  }, [phase, ready]);

  useEffect(() => {
    if (!ready || still) return;
    let lastMove = 0;
    const onMove = (event: PointerEvent) => {
      const box = holder.current?.getBoundingClientRect();
      if (!box) return;
      lastMove = performance.now();
      const dx = (event.clientX - (box.left + box.width / 2)) / Math.max(window.innerWidth / 2, 1);
      const dy = (event.clientY - (box.top + box.height * 0.35)) / Math.max(window.innerHeight / 2, 1);
      controller.current?.lookAt({ yaw: Math.max(-1, Math.min(1, dx)) * 28, pitch: Math.max(-1, Math.min(1, dy)) * 14 });
    };
    const wander = window.setInterval(() => {
      if (performance.now() - lastMove < IDLE_MS) return;
      controller.current?.lookAt({ yaw: (Math.random() - 0.5) * 30, pitch: (Math.random() - 0.5) * 12 });
    }, 2600);
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.clearInterval(wander);
    };
  }, [ready, still]);

  return (
    <div ref={holder} className={`robot3d${ready ? " ready" : ""}`}>
      {!ready && <Robot />}
      <canvas ref={canvas} aria-hidden="true" />
    </div>
  );
}
