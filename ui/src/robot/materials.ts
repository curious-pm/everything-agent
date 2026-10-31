import { Color, MeshStandardMaterial } from "three";

export type Part = "shell" | "dark" | "eye";

const EYES = new Set(["big_lens_d40.stl", "small_lens_d30.stl"]);
const DARK_PREFIXES = ["antenna.stl", "dc15_", "mp01062", "stewart_link", "bearing", "5w_speaker", "bts2", "b3b_", "phs_", "arducam", "pp01102", "m12_", "lens_cap", "glasses_dolder", "stewart_tricap", "stewart_main_plate"];

export function partFor(file: string): Part {
  const name = file.split(/[\\/]/).pop()?.toLowerCase() ?? "";
  if (EYES.has(name)) return "eye";
  if (DARK_PREFIXES.some((p) => name.startsWith(p))) return "dark";
  return "shell";
}

export function makeMaterials() {
  return {
    shell: new MeshStandardMaterial({ color: new Color("#f3f2ef"), roughness: 0.6, metalness: 0.02 }),
    dark: new MeshStandardMaterial({ color: new Color("#2b3037"), roughness: 0.5, metalness: 0.15 }),
    eye: new MeshStandardMaterial({ color: new Color("#0d0f12"), roughness: 0.15, metalness: 0.2, emissive: new Color("#3f7bff"), emissiveIntensity: 0.9 }),
  };
}
