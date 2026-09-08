export interface HealthResponse {
  status: string;
  database: string;
  checked_at: string;
}

export interface Pitcher {
  player_id: number;
  mlb_id: number | null;
  player_name: string;
  throws: "L" | "R" | null;
  pitch_count: number;
  game_count: number;
  first_game: string;
  last_game: string;
}

export interface Game {
  game_pk: number;
  game_date: string;
  home_team: string;
  away_team: string;
  pitch_count: number;
  video_count: number;
}

export interface PitcherGamesResponse {
  pitcher: Pick<
    Pitcher,
    "player_id" | "mlb_id" | "player_name" | "throws"
  >;
  games: Game[];
}

export interface Pitch {
  pitch_id: string;
  game_pk: number;
  pitcher_id: number;
  batter_id: number | null;
  pitcher_name: string;
  batter_name: string | null;
  game_date: string;
  home_team: string;
  away_team: string;
  at_bat_number: number;
  pitch_number: number;
  inning: number | null;
  inning_half: string | null;
  batter_side: "L" | "R" | null;
  pitch_type: string;
  velocity: number | null;
  spin_rate: number | null;
  horizontal_break: number | null;
  vertical_break: number | null;
  release_extension: number | null;
  plate_x: number | null;
  plate_z: number | null;
  balls: number;
  strikes: number;
  description: string | null;
  events: string | null;
  exit_velocity: number | null;
  launch_angle: number | null;
  video_url: string | null;
  video_available: boolean;
}

export interface PitchSearchResponse {
  total: number;
  limit: number;
  offset: number;
  pitches: Pitch[];
}

export interface PitchSearchFilters {
  pitcher_id: number;
  game_pk: number | null;
  batter_side: "" | "L" | "R";
  pitch_type: string;
  balls: number | null;
  strikes: number | null;
  result: string;
  min_velocity: number | null;
  max_velocity: number | null;
  min_plate_x: number | null;
  max_plate_x: number | null;
  min_plate_z: number | null;
  max_plate_z: number | null;
  video_available: boolean | null;
  limit: number;
  offset: number;
}

export interface PlaylistRecord {
  playlist_id: number;
  playlist_name: string;
  description: string | null;
  created_at: string;
}

export interface PlaylistSummary extends PlaylistRecord {
  item_count: number;
  video_count: number;
}

export interface PlaylistItem extends Pitch {
  display_order: number;
  scouting_note: string | null;
}

export interface PlaylistDetail extends PlaylistRecord {
  items: PlaylistItem[];
}

export interface PlaylistWrite {
  playlist_name: string;
  description: string | null;
}

export interface PlaylistItemsWrite {
  items: Array<{
    pitch_id: string;
    scouting_note: string | null;
  }>;
}

export interface ApiErrorBody {
  detail?: string;
  message?: string;
}
