// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { readRootEnv, writeRootEnv } from '@/lib/env-sync';

export async function GET() {
  try {
    return NextResponse.json({ content: readRootEnv() });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const content = typeof body?.content === 'string' ? body.content : '';
    writeRootEnv(content);
    // MCPs load .env only at startup, so any change is restart-required.
    return NextResponse.json({ ok: true, restartRequired: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
