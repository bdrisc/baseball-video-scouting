const SAVANT = "https://baseballsavant.mlb.com/sporty-videos";
const MAX_HTML_BYTES = 256_000;

export const PLAY_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function extractOfficialClip(html: string, playId: string): string | null {
  if (!PLAY_ID_PATTERN.test(playId)) return null;
  const video = html.match(/<video\b([^>]*)>([\s\S]*?)<\/video>/gi)?.find((tag) =>
    /\bid=["']sporty["']/i.test(tag.split(">", 1)[0]),
  );
  if (!video) return null;
  const opening = video.slice(0, video.indexOf(">"));
  const classId = opening.match(/\bclassid=["']([^"']+)["']/i)?.[1];
  if (classId?.toLowerCase() !== playId.toLowerCase()) return null;
  const source = video.match(/<source\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/i)?.[1];
  if (!source) return null;
  try {
    const url = new URL(source);
    if (
      url.protocol !== "https:" ||
      url.hostname !== "sporty-clips.mlb.com" ||
      !url.pathname.toLowerCase().endsWith(".mp4") ||
      url.username || url.password
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

export async function resolveOfficialClip(
  playId: string,
  fetcher: typeof fetch = fetch,
): Promise<string | null> {
  if (!PLAY_ID_PATTERN.test(playId)) return null;
  const response = await fetcher(`${SAVANT}?playId=${playId}`, {
    headers: { Accept: "text/html" },
    redirect: "error",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok || !response.headers.get("content-type")?.includes("text/html")) return null;
  const reader = response.body?.getReader();
  if (!reader) return null;
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_HTML_BYTES) return null;
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
  const html = new TextDecoder().decode(Buffer.concat(chunks));
  return extractOfficialClip(html, playId);
}
