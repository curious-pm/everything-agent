import { cpSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const site = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(site, "dist");
const root = join(site, "..");

rmSync(join(root, "site-assets"), { recursive: true, force: true });
for (const name of ["index.html", "style.css", "site.js", "site-assets"]) {
  cpSync(join(dist, name), join(root, name), { recursive: true });
}
console.log("Published the site to the repository root.");
