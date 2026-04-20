import { NextRequest, NextResponse } from "next/server";
import { parseSortSpec, queryData } from "@/lib/license-data";

function isTruthy(value: string | null) {
  if (!value) return false;
  const v = value.toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams;

    const page = Number(sp.get("page") || "1");
    const pageSize = Number(sp.get("pageSize") || "25");
    const sort = parseSortSpec(sp.get("sort") || "confidence:desc");

    const result = queryData({
      page: Number.isNaN(page) ? 1 : page,
      pageSize: Number.isNaN(pageSize) ? 25 : pageSize,
      sort,
      filters: {
        search: (sp.get("search") || "").trim().toLowerCase(),
        category: (sp.get("category") || "").trim().toLowerCase(),
        year: (sp.get("year") || "").trim(),
        minConfidence: sp.get("minConfidence")
          ? Number(sp.get("minConfidence"))
          : null,
        excludeMissingLicensor: isTruthy(sp.get("excludeMissingLicensor")),
        excludeMissingLicensee: isTruthy(sp.get("excludeMissingLicensee")),
        excludeMissingRoyalty: isTruthy(sp.get("excludeMissingRoyalty")),
        excludeMissingUpfront: isTruthy(sp.get("excludeMissingUpfront")),
        excludeMissingConfidence: isTruthy(sp.get("excludeMissingConfidence")),
      },
    });

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    return NextResponse.json(
      { error: "Failed to load license data", detail: message },
      { status: 500 },
    );
  }
}
