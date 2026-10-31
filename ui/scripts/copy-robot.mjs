import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "../public/robot");

function pythonCandidates() {
  const list = [];
  if (process.env.REACHY_PYTHON) list.push(process.env.REACHY_PYTHON);
  for (const venv of ["../.venv", "../../.venv"]) {
    list.push(resolve(here, "..", venv, "Scripts/python.exe"), resolve(here, "..", venv, "bin/python"));
  }
  list.push("python3", "python");
  return list;
}

function findPackage() {
  for (const python of pythonCandidates()) {
    const isPath = python.includes("/") || python.includes("\\");
    if (isPath && !existsSync(python)) continue;
    try {
      const path = execFileSync(python, ["-c", "import reachy_mini, os; print(os.path.dirname(reachy_mini.__file__))"], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
      if (path) return path;
    } catch {}
  }
  throw new Error("Couldn't find the reachy_mini package. Set REACHY_PYTHON to the Python that has it installed.");
}

const urdfDir = join(findPackage(), "descriptions", "reachy_mini", "urdf");
const urdf = readFileSync(join(urdfDir, "robot_no_collision.urdf"), "utf8");
const meshes = [...new Set([...urdf.matchAll(/filename="package:\/\/assets\/([^"]+)"/g)].map((m) => m[1]))];

rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "assets"), { recursive: true });
writeFileSync(join(out, "robot.urdf"), urdf);
for (const mesh of meshes) copyFileSync(join(urdfDir, "assets", mesh), join(out, "assets", mesh));
console.log(`robot model: ${meshes.length} meshes from ${urdfDir}`);
