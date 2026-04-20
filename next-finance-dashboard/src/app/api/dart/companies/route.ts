import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export async function GET() {
  try {
    const basePath = resolveBasePath();
    const dirs = fs
      .readdirSync(basePath, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .filter((e) => !e.name.startsWith("run_summary"));

    const companies: Array<{ id: string; name: string; filingCount: number }> = [];

    for (const dir of dirs) {
      const dirPath = path.join(basePath, dir.name);
      const jsonFiles = fs
        .readdirSync(dirPath)
        .filter((f) => f.endsWith(".json"))
        .sort();

      let companyName = dir.name;
      if (jsonFiles.length > 0) {
        try {
          const data = JSON.parse(
            fs.readFileSync(path.join(dirPath, jsonFiles[0]), "utf-8"),
          );
          companyName = data?.company?.name || dir.name;
        } catch {
          // keep dir name
        }
      }

      companies.push({
        id: dir.name,
        name: companyName,
        filingCount: jsonFiles.length,
      });
    }

    companies.sort((a, b) => b.filingCount - a.filingCount || a.name.localeCompare(b.name));

    return NextResponse.json({ total: companies.length, companies });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown";
    return NextResponse.json({ error: detail }, { status: 500 });
  }
}

function resolveBasePath(): string {
  const candidates = [
    process.env.DART_UNIFIED_SCHEMA_PATH,
    path.resolve(process.cwd(), "../data/dart/unified_schema"),
    path.resolve(process.cwd(), "../../data/dart/unified_schema"),
    path.resolve(process.cwd(), "data/dart/unified_schema"),
  ].filter(Boolean) as string[];

  for (const p of candidates) {
    if (fs.existsSync(p) && fs.statSync(p).isDirectory()) return p;
  }
  throw new Error(`DART path not found: ${candidates.join(", ")}`);
}
