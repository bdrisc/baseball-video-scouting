import type { Pitch } from "../types/api";

interface PitchDetailsProps {
  pitch: Pitch | null;
  scoutingNote: string;
  onScoutingNoteChange: (note: string) => void;
}

const pitchNames: Record<string, string> = {
  CH: "Changeup",
  CS: "Slow Curve",
  CU: "Curveball",
  EP: "Eephus",
  FA: "Fastball",
  FC: "Cutter",
  FF: "Four-Seam Fastball",
  FO: "Forkball",
  FS: "Splitter",
  KC: "Knuckle Curve",
  KN: "Knuckleball",
  PO: "Pitchout",
  SC: "Screwball",
  SI: "Sinker",
  SL: "Slider",
  ST: "Sweeper",
  SV: "Slurve",
};

function numberOrDash(value: number | null, decimals = 1): string {
  return value === null ? "—" : value.toFixed(decimals);
}

function signedInches(value: number | null): string {
  if (value === null) return "—";
  const inches = value * 12;
  return `${inches > 0 ? "+" : ""}${inches.toFixed(1)} in`;
}

function readableResult(value: string | null): string {
  if (!value) return "—";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function combinedResult(pitch: Pitch): string {
  const values = [pitch.description, pitch.events]
    .filter((value): value is string => Boolean(value))
    .filter((value, index, allValues) => allValues.indexOf(value) === index)
    .map(readableResult);
  return values.join(" · ") || "—";
}

export default function PitchDetails({
  pitch,
  scoutingNote,
  onScoutingNoteChange,
}: PitchDetailsProps) {
  return (
    <section className="panel detail-panel" aria-live="polite">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Selected pitch</p>
          <h2>Pitch details</h2>
        </div>
        {pitch ? <span className="result-count">{pitch.pitch_id}</span> : null}
      </div>

      {pitch ? (
        <div className="pitch-detail-content">
          <div className="pitch-detail-hero">
            <span className={`pitch-code pitch-${pitch.pitch_type.toLowerCase()}`}>
              {pitch.pitch_type}
            </span>
            <div>
              <strong>{pitchNames[pitch.pitch_type] ?? pitch.pitch_type}</strong>
              <span>
                {pitch.game_date} · {pitch.away_team} at {pitch.home_team}
              </span>
            </div>
            <div className="hero-reading">
              <strong>{numberOrDash(pitch.velocity)} mph</strong>
              <span>
                {pitch.balls}-{pitch.strikes} count
              </span>
            </div>
          </div>

          <dl className="detail-grid expanded-details">
            <div>
              <dt>Spin rate</dt>
              <dd>{numberOrDash(pitch.spin_rate, 0)} rpm</dd>
            </div>
            <div>
              <dt>Release extension</dt>
              <dd>{numberOrDash(pitch.release_extension)} ft</dd>
            </div>
            <div>
              <dt>Horizontal movement</dt>
              <dd>{signedInches(pitch.horizontal_break)}</dd>
            </div>
            <div>
              <dt>Vertical movement</dt>
              <dd>{signedInches(pitch.vertical_break)}</dd>
            </div>
            <div>
              <dt>Batter</dt>
              <dd>
                {pitch.batter_name ?? "Unavailable"}
                {pitch.batter_side ? ` (${pitch.batter_side})` : ""}
              </dd>
            </div>
            <div>
              <dt>Plate location</dt>
              <dd>
                X {numberOrDash(pitch.plate_x, 2)} ft · Z{" "}
                {numberOrDash(pitch.plate_z, 2)} ft
              </dd>
            </div>
            <div className="wide-detail">
              <dt>Result</dt>
              <dd>{combinedResult(pitch)}</dd>
            </div>
            {pitch.exit_velocity !== null || pitch.launch_angle !== null ? (
              <>
                <div>
                  <dt>Exit velocity</dt>
                  <dd>{numberOrDash(pitch.exit_velocity)} mph</dd>
                </div>
                <div>
                  <dt>Launch angle</dt>
                  <dd>{numberOrDash(pitch.launch_angle, 0)}°</dd>
                </div>
              </>
            ) : null}
          </dl>

          <label className="notes-field">
            <span>Scouting notes</span>
            <textarea
              value={scoutingNote}
              maxLength={2000}
              rows={4}
              placeholder="Record pitch shape, intent, execution, sequencing, or hitter reaction…"
              onChange={(event) => onScoutingNoteChange(event.target.value)}
            />
            <span className="notes-meta">
              Draft for this session · {scoutingNote.length}/2,000 characters
            </span>
          </label>

          {pitch.video_available && pitch.video_url ? (
            <a
              className="primary-button detail-video-button"
              href={pitch.video_url}
              target="_blank"
              rel="noreferrer"
            >
              Watch official MLB video
            </a>
          ) : (
            <button
              className="primary-button detail-video-button"
              type="button"
              disabled
            >
              Video unavailable
            </button>
          )}
        </div>
      ) : (
        <div className="empty-state compact">
          <strong>Select a pitch to inspect it.</strong>
          <span>
            Click any results-table row to view its metrics, outcome, video,
            and scouting-notes field.
          </span>
        </div>
      )}
    </section>
  );
}
