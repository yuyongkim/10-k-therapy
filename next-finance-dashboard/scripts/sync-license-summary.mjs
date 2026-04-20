import fs from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();

const explicit = process.env.LICENSE_SUMMARY_PATH
  ? path.resolve(process.env.LICENSE_SUMMARY_PATH)
  : null;

const targetPath = path.resolve(projectRoot, "license_summary.json");
const candidates = [
  explicit,
  path.resolve(projectRoot, "..", "license_summary.json"),
  path.resolve(projectRoot, "license_summary.json"),
].filter(Boolean);

function findSource() {
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }
  return null;
}

const sourcePath = findSource();

if (!sourcePath) {
  console.error("[sync-license-summary] Could not find license_summary.json.");
  console.error(`[sync-license-summary] Checked: ${candidates.join(", ")}`);
  process.exit(1);
}

if (path.resolve(sourcePath) === targetPath) {
  const sizeMb = (fs.statSync(targetPath).size / 1_000_000).toFixed(2);
  console.log(`[sync-license-summary] Using in-place file: ${targetPath} (${sizeMb} MB)`);
  process.exit(0);
}

fs.copyFileSync(sourcePath, targetPath);

const stat = fs.statSync(targetPath);
const sizeMb = (stat.size / 1_000_000).toFixed(2);
console.log(`[sync-license-summary] Copied ${sourcePath} -> ${targetPath} (${sizeMb} MB)`);
