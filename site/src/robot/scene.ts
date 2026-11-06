import {
  ACESFilmicToneMapping,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  DirectionalLight,
  Group,
  HemisphereLight,
  LoadingManager,
  Mesh,
  MeshBasicMaterial,
  Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  WebGLRenderer,
} from "three";
import URDFLoader from "urdf-loader";
import { StewartSolver } from "./kinematics";
import { makeMaterials, partFor } from "./materials";
import manifest from "./meshes.json";
import meshesUrl from "./meshes.bin?url";
import { clampLook, postureFor, type Look } from "./poses";
import urdfText from "./robot.urdf?raw";

export type Mood = "listening" | "thinking" | "speaking";

export type RobotController = {
  lookAt(look: Partial<Look>): void;
  setMood(mood: Mood, color: string): void;
  dispose(): void;
};

type MeshInfo = { offset: number; vertices: number; indices: number; wide: boolean; min: number[]; span: number[] };

const TARGET: [number, number, number] = [0, 0.16, 0];
const CAMERA: [number, number, number] = [0.68, 0.27, 0.24];
const MAX_DEG_PER_S = 70;

function geometryFrom(buffer: ArrayBuffer, info: MeshInfo): BufferGeometry {
  const raw = new Uint16Array(buffer, info.offset, info.vertices * 3);
  const positions = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    const axis = i % 3;
    positions[i] = info.min[axis] + (raw[i] / 65535) * info.span[axis];
  }
  let indexOffset = info.offset + info.vertices * 6;
  indexOffset += (4 - (indexOffset % 4)) % 4;
  const index = info.wide
    ? new Uint32Array(buffer, indexOffset, info.indices)
    : new Uint16Array(buffer, indexOffset, info.indices);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(positions, 3));
  geometry.setIndex(new BufferAttribute(index, 1));
  geometry.computeVertexNormals();
  return geometry;
}

function glowTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new CanvasTexture(canvas);
}

export async function mountRobot(canvas: HTMLCanvasElement, options: { still: boolean }): Promise<RobotController> {
  const buffer = await (await fetch(meshesUrl)).arrayBuffer();
  const meshes = manifest as Record<string, MeshInfo>;
  const materials = makeMaterials();

  const loader = new URDFLoader(new LoadingManager());
  loader.packages = { assets: "" };
  loader.loadMeshCb = (url, _manager, done) => {
    const name = url.split("/").pop() ?? "";
    const info = meshes[name];
    if (!info) {
      done(new Object3D());
      return;
    }
    const mesh = new Mesh(geometryFrom(buffer, info));
    done(mesh);
    mesh.material = materials[partFor(name)];
  };
  const model = loader.parse(urdfText);
  const solver = new StewartSolver(new DOMParser().parseFromString(urdfText, "text/xml"));

  const renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = ACESFilmicToneMapping;
  const scene = new Scene();
  const camera = new PerspectiveCamera(30, 1, 0.01, 10);
  camera.position.set(...CAMERA);
  camera.lookAt(...TARGET);
  scene.add(new HemisphereLight("#ffffff", "#b9bdbb", 2.4));
  const key = new DirectionalLight("#ffffff", 2.6);
  key.position.set(0.8, 1.4, 0.6);
  scene.add(key);
  const rim = new DirectionalLight("#ffffff", 0.9);
  rim.position.set(-0.6, 0.4, -0.8);
  scene.add(rim);

  const root = new Group();
  model.rotation.x = -Math.PI / 2;
  root.add(model);
  const glow = new Mesh(
    new PlaneGeometry(0.34, 0.34),
    new MeshBasicMaterial({ map: glowTexture(), color: new Color("#3f7bff"), transparent: true, opacity: 0.4, depthWrite: false }),
  );
  glow.rotation.x = -Math.PI / 2;
  glow.position.y = -0.001;
  root.add(glow);
  scene.add(root);

  let mood: Mood = "listening";
  const target: Look = { yaw: 0, pitch: 0, roll: 0 };
  const current: Look = { yaw: 0, pitch: 0, roll: 0 };
  let frame = 0;
  let last = performance.now();
  let onScreen = true;
  let running = true;

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = canvas;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const sizer = new ResizeObserver(resize);
  sizer.observe(canvas);
  resize();

  const pose = (time: number) => {
    const t = time / 1000;
    const thinking = mood === "thinking";
    const speaking = mood === "speaking";
    const aim = {
      yaw: target.yaw,
      pitch: target.pitch + (thinking ? -7 : 0) + (speaking && !options.still ? Math.sin(t * 5.2) * 2.5 : 0),
      roll: target.roll + (thinking ? 8 : 0),
    };
    const dt = Math.min(0.1, (time - last) / 1000);
    last = time;
    const step = MAX_DEG_PER_S * dt;
    for (const axis of ["yaw", "pitch", "roll"] as const) {
      const gap = aim[axis] - current[axis];
      current[axis] += options.still ? gap : Math.max(-step, Math.min(step, gap * Math.min(1, dt * 6)));
    }
    const { headPose, headJoints } = postureFor(clampLook(current));
    const q = solver.solve(headPose, headJoints);
    const wiggle = options.still ? 0 : speaking ? 0.38 : mood === "listening" ? 0.06 : 0;
    const lean = thinking ? -0.35 : 0;
    q.right_antenna = lean + wiggle * Math.sin(t * 7.1);
    q.left_antenna = -lean - wiggle * Math.sin(t * 6.3 + 1.2);
    model.setJointValues(q);
  };

  const tick = (time: number) => {
    if (!running) return;
    frame = requestAnimationFrame(tick);
    if (!onScreen || document.hidden) {
      last = time;
      return;
    }
    pose(time);
    renderer.render(scene, camera);
  };

  const visibility = new IntersectionObserver((entries) => {
    onScreen = entries.some((e) => e.isIntersecting);
  });
  visibility.observe(canvas);

  pose(performance.now());
  renderer.render(scene, camera);
  if (!options.still) frame = requestAnimationFrame(tick);

  return {
    lookAt(look) {
      Object.assign(target, look);
      if (options.still) {
        pose(performance.now());
        renderer.render(scene, camera);
      }
    },
    setMood(next, color) {
      mood = next;
      materials.eye.emissive = new Color(color);
      (glow.material as MeshBasicMaterial).color = new Color(color);
      if (options.still) {
        pose(performance.now());
        renderer.render(scene, camera);
      }
    },
    dispose() {
      running = false;
      cancelAnimationFrame(frame);
      sizer.disconnect();
      visibility.disconnect();
      renderer.dispose();
    },
  };
}
