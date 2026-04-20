import { NextRequest, NextResponse } from "next/server";
import { queryDartData } from "@/lib/dart-data";

export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams;
    const companyId = (sp.get("company") || "").trim();
    const filing = (sp.get("filing") || "").trim();

    const result = queryDartData({
      companyId: companyId || undefined,
      filing: filing || undefined,
    });

    return NextResponse.json(result);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown error";
    return NextResponse.json(
      { error: "Failed to load DART data", detail },
      { status: 500 },
    );
  }
}

