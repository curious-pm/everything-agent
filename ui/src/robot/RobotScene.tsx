import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import { CanvasTexture, Color, LoadingManager, type Mesh } from "three";
import URDFLoader, { type URDFRobot } from "urdf-loader";
import { StewartSolver } from "./kinematics";
import { makeMaterials, partFor } from "./materials";
import { streamRobot, type RobotFrame } from "./robotStream";

export type StreamStatus = "loading" | "live" | "offline";

export type RobotSceneProps = {
  stateColor: string;
  speakerLevel: number;
  onStatus?: (status: StreamStatus) => void;
};

const MAX_FPS = 20;
const TARGET: [number, number, number] = [0, 0.14, 0];
const CAMERA: [number, number, number] = [0.68, 0.34, 0];
const SHELL_VISIBILITY_EVENT = "everything-agent-visibility";

function radialTexture(inner: string, outer: string): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, inner);
  g.addColorStop(1, outer);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new CanvasTexture(canvas);
}

function usePageVisible(): boolean {
  const [visible, setVisible] = useState(document.visibilityState === "visible");
  useEffect(() => {
    const onVisibility = () => setVisible(document.visibilityState === "visible");
    const onShell = (e: Event) => setVisible(Boolean((e as CustomEvent<boolean>).detail));
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener(SHELL_VISIBILITY_EVENT, onShell);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener(SHELL_VISIBILITY_EVENT, onShell);
    };
  }, []);
  return visible;
}

function Robot({ stateColor, visible, onStatus }: { stateColor: string; visible: boolean; onStatus?: RobotSceneProps["onStatus"] }) {
  const invalidate = useThree((s) => s.invalidate);
  const [robot, setRobot] = useState<{ model: URDFRobot; solver: StewartSolver } | null>(null);
  const materials = useMemo(() => makeMaterials(), []);
  const latest = useRef<RobotFrame | null>(null);
  const lastDraw = useRef(0);
  const visibleRef = useRef(visible);

  useEffect(() => {
    visibleRef.current = visible;
    if (visible) invalidate();
  }, [visible, invalidate]);

  useEffect(() => {
    let cancelled = false;
    fetch("./robot/robot.urdf")
      .then((r) => r.text())
      .then((text) => {
        const loader = new URDFLoader(new LoadingManager());
        loader.packages = { assets: "./robot/assets" };
        loader.loadMeshCb = (url, manager, done) =>
          loader.defaultMeshLoader(url, manager, (obj, err) => {
            done(obj, err);
            obj?.traverse((o) => {
              if ((o as Mesh).isMesh) (o as Mesh).material = materials[partFor(url)];
            });
            invalidate();
          });
        const model = loader.parse(text);
        const solver = new StewartSolver(new DOMParser().parseFromString(text, "text/xml"));
        if (!cancelled) setRobot({ model, solver });
      })
      .catch(() => onStatus?.("offline"));
    return () => {
      cancelled = true;
    };
  }, [materials, invalidate, onStatus]);

  useEffect(() => {
    materials.eye.emissive = new Color(stateColor);
    invalidate();
  }, [stateColor, materials, invalidate]);

  useEffect(
    () =>
      streamRobot(
        (frame) => {
          latest.current = frame;
          const now = performance.now();
          if (visibleRef.current && now - lastDraw.current >= 1000 / MAX_FPS) {
            lastDraw.current = now;
            invalidate();
          }
        },
        (open) => onStatus?.(open ? "live" : "offline"),
      ),
    [invalidate, onStatus],
  );

  useFrame(() => {
    const frame = latest.current;
    if (!robot || !frame) return;
    latest.current = null;
    const q = robot.solver.solve(frame.headPose, frame.headJoints);
    q.right_antenna = frame.antennas[0];
    q.left_antenna = frame.antennas[1];
    robot.model.setJointValues(q);
  });

  if (!robot) return null;
  return <primitive object={robot.model} rotation={[-Math.PI / 2, 0, 0]} />;
}

function Floor({ stateColor, speakerLevel }: { stateColor: string; speakerLevel: number }) {
  const glow = useMemo(() => radialTexture("rgba(255,255,255,1)", "rgba(255,255,255,0)"), []);
  const shadow = useMemo(() => radialTexture("rgba(0,0,0,0.45)", "rgba(0,0,0,0)"), []);
  const invalidate = useThree((s) => s.invalidate);
  const glowOpacity = 0.35 + Math.min(0.45, speakerLevel * 3);
  useEffect(() => invalidate(), [glowOpacity, stateColor, invalidate]);
  return (
    <group rotation={[-Math.PI / 2, 0, 0]}>
      <mesh position={[0, 0, -0.001]}>
        <planeGeometry args={[0.46, 0.46]} />
        <meshBasicMaterial map={glow} color={stateColor} transparent opacity={glowOpacity} depthWrite={false} />
      </mesh>
      <mesh>
        <planeGeometry args={[0.24, 0.24]} />
        <meshBasicMaterial map={shadow} transparent depthWrite={false} />
      </mesh>
    </group>
  );
}

export default function RobotScene({ stateColor, speakerLevel, onStatus }: RobotSceneProps) {
  const visible = usePageVisible();
  return (
    <Canvas
      frameloop="demand"
      dpr={1}
      gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
      camera={{ position: CAMERA, fov: 32, near: 0.01, far: 10 }}
    >
      <hemisphereLight args={["#ffffff", "#b9bdbb", 1.25]} />
      <directionalLight position={[0.8, 1.4, 0.6]} intensity={1.5} />
      <directionalLight position={[-0.6, 0.4, -0.8]} intensity={0.35} />
      <Robot stateColor={stateColor} visible={visible} onStatus={onStatus} />
      <Floor stateColor={stateColor} speakerLevel={speakerLevel} />
      <OrbitControls
        target={TARGET}
        enablePan={false}
        minDistance={0.3}
        maxDistance={1.4}
        minPolarAngle={0.2}
        maxPolarAngle={Math.PI / 2 - 0.05}
        makeDefault
      />
    </Canvas>
  );
}
