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
  team_codes?: string[];
}

export interface SeasonSummary {
  season: number;
  game_count: number;
  pitcher_count: number;
  pitch_count: number;
  first_game: string;
  last_game: string;
}

export interface TeamSummary {
  team_id: number;
  team_code: string;
  team_name: string;
  game_count: number;
  pitcher_count: number;
  pitch_count: number;
}

export interface PitcherSearchFilters {
  q: string;
  season: number | null;
  team_id: number | null;
  throws: "" | "L" | "R";
  limit: number;
  offset: number;
}

export interface PitcherSearchResponse {
  total: number;
  limit: number;
  offset: number;
  has_previous: boolean;
  has_next: boolean;
  pitchers: Pitcher[];
}

export interface Game {
  game_pk: number;
  game_date: string;
  home_team: string;
  away_team: string;
  pitch_count: number;
  video_count: number;
  season: number;
  pitcher_team: string | null;
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
  sort_by: PitchSortField;
  sort_order: SortOrder;
  has_previous: boolean;
  has_next: boolean;
  pitches: Pitch[];
}

export type PitchSortField =
  | "game_date"
  | "batter_name"
  | "pitch_type"
  | "velocity"
  | "spin_rate"
  | "inning"
  | "result";

export type SortOrder = "asc" | "desc";

export interface PitchSearchFilters {
  pitcher_id: number;
  game_pk: number | null;
  season: number | null;
  team_id: number | null;
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
  sort_by: PitchSortField;
  sort_order: SortOrder;
}

export type PitchAggregateFilters = Omit<
  PitchSearchFilters,
  "limit" | "offset" | "sort_by" | "sort_order"
>;

export interface PitchAggregateSummary {
  total_pitches: number;
  average_velocity: number | null;
  whiffs: number;
  videos_available: number;
  pitch_types: number;
}

export interface PitchUsageAggregate {
  pitch_type: string;
  pitch_count: number;
  usage_percent: number;
}

export interface VelocityByInningAggregate {
  pitch_type: string;
  inning: number;
  pitch_count: number;
  average_velocity: number;
}

export interface UsageByCountAggregate {
  pitch_type: string;
  balls: number;
  strikes: number;
  pitch_count: number;
  usage_percent: number;
}

export type ResultGroup =
  | "Ball"
  | "Called strike"
  | "Whiff"
  | "Foul"
  | "In play"
  | "Other";

export interface BatterSideResultAggregate {
  batter_side: "L" | "R";
  result_group: ResultGroup;
  pitch_count: number;
  percentage: number;
}

export interface ArsenalAggregate {
  pitch_type: string;
  count: number;
  usage: number;
  average_velocity: number | null;
  average_spin: number | null;
  horizontal_break: number | null;
  vertical_break: number | null;
  whiff_rate: number | null;
  zone_rate: number | null;
}

export interface CountTendencyAggregate {
  label: string;
  sample_size: number;
  top_pitch: string;
  usage: number | null;
}

export interface HandednessAggregate {
  side: "L" | "R";
  count: number;
  pitch_mix: Array<{
    pitch_type: string;
    usage: number;
  }>;
  whiff_rate: number | null;
  zone_rate: number | null;
}

export interface ReportAggregate {
  arsenal: ArsenalAggregate[];
  usage_summary: string;
  count_tendencies: CountTendencyAggregate[];
  handedness: HandednessAggregate[];
  location: {
    sample_size: number;
    zone_rate: number | null;
    primary_vertical_band: string;
    primary_horizontal_lane: string;
    fastball_elevated_rate: number | null;
  };
  putaway: {
    sample_size: number;
    top_pitch: string;
    top_pitch_usage: number | null;
    whiff_rate: number | null;
    strikeouts: number;
    best_whiff_pitch: string;
  };
  damage: {
    balls_in_play: number;
    average_exit_velocity: number | null;
    hard_hit_rate: number | null;
    maximum_exit_velocity: number | null;
    home_runs: number;
    most_damaged_pitch: string;
  };
}

export interface PitchAggregateResponse {
  total: number;
  summary: PitchAggregateSummary;
  pitch_usage: PitchUsageAggregate[];
  velocity_by_inning: VelocityByInningAggregate[];
  usage_by_count: UsageByCountAggregate[];
  results_by_batter_side: BatterSideResultAggregate[];
  report: ReportAggregate;
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
