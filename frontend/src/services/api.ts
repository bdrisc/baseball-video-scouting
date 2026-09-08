import type {
  ApiErrorBody,
  HealthResponse,
  PlaylistDetail,
  PlaylistItemsWrite,
  PlaylistRecord,
  PlaylistSummary,
  PlaylistWrite,
  PitchSearchFilters,
  PitchSearchResponse,
  Pitcher,
  PitcherGamesResponse,
} from "../types/api";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

interface RequestOptions {
  signal?: AbortSignal;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { signal, method = "GET", body } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const body = (await response.json()) as ApiErrorBody;
      message = body.detail ?? body.message ?? message;
    } catch {
      // Keep the status-based fallback when the server does not return JSON.
    }

    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function getPitchers(signal?: AbortSignal): Promise<Pitcher[]> {
  return request<Pitcher[]>("/pitchers", { signal });
}

export function getPitcherGames(
  pitcherId: number,
  signal?: AbortSignal,
): Promise<PitcherGamesResponse> {
  return request<PitcherGamesResponse>(
    `/pitchers/${pitcherId}/games`,
    { signal },
  );
}

export function getPitches(
  filters: PitchSearchFilters,
  signal?: AbortSignal,
): Promise<PitchSearchResponse> {
  const parameters = new URLSearchParams();

  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== "") {
      parameters.set(key, String(value));
    }
  }

  return request<PitchSearchResponse>(`/pitches?${parameters.toString()}`, {
    signal,
  });
}

export function getPlaylists(signal?: AbortSignal): Promise<PlaylistSummary[]> {
  return request<PlaylistSummary[]>("/playlists", { signal });
}

export function getPlaylist(
  playlistId: number,
  signal?: AbortSignal,
): Promise<PlaylistDetail> {
  return request<PlaylistDetail>(`/playlists/${playlistId}`, { signal });
}

export function createPlaylist(body: PlaylistWrite): Promise<PlaylistRecord> {
  return request<PlaylistRecord>("/playlists", { method: "POST", body });
}

export function updatePlaylist(
  playlistId: number,
  body: PlaylistWrite,
): Promise<PlaylistRecord> {
  return request<PlaylistRecord>(`/playlists/${playlistId}`, {
    method: "PUT",
    body,
  });
}

export function savePlaylistItems(
  playlistId: number,
  body: PlaylistItemsWrite,
): Promise<PlaylistDetail> {
  return request<PlaylistDetail>(`/playlists/${playlistId}/items`, {
    method: "PUT",
    body,
  });
}
