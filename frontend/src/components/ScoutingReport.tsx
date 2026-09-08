import { useEffect, useMemo, useState } from "react";

import type { Pitch, PlaylistDetail } from "../types/api";
import { pitchLabel } from "./chartHelpers";
import { buildReportMetrics } from "./reportMetrics";

interface ScoutingReportProps {
  pitches: Pitch[];
  totalMatches: number;
  pitcherName: string | null;
  activePlaylist: PlaylistDetail | null;
}

function formatNumber(value: number | null, decimals = 1): string {
  return value === null ? "—" : value.toFixed(decimals);
}

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function signedBreak(value: number | null): string {
  if (value === null) return "—";
  const inches = value * 12;
  return `${inches > 0 ? "+" : ""}${inches.toFixed(1)}`;
}

export default function ScoutingReport({
  pitches,
  totalMatches,
  pitcherName,
  activePlaylist,
}: ScoutingReportProps) {
  const metrics = useMemo(() => buildReportMetrics(pitches), [pitches]);
  const observationKey = `advance-report-observations:${
    activePlaylist?.playlist_id ?? pitches[0]?.pitcher_id ?? "general"
  }`;
  const [observations, setObservations] = useState("");
  const [loadedObservationKey, setLoadedObservationKey] = useState("");
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

  useEffect(() => {
    setObservations(window.localStorage.getItem(observationKey) ?? "");
    setLoadedObservationKey(observationKey);
    setCopyMessage(null);
  }, [observationKey]);

  useEffect(() => {
    if (loadedObservationKey === observationKey) {
      window.localStorage.setItem(observationKey, observations);
    }
  }, [loadedObservationKey, observationKey, observations]);

  const playlistUrl = useMemo(() => {
    if (!activePlaylist) return null;
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("playlist", String(activePlaylist.playlist_id));
    return url.toString();
  }, [activePlaylist]);

  async function copyPlaylistLink() {
    if (!playlistUrl) return;
    try {
      await navigator.clipboard.writeText(playlistUrl);
      setCopyMessage("Playlist link copied.");
    } catch {
      setCopyMessage("Could not copy automatically. Open the link and copy the address.");
    }
  }

  return (
    <section className="panel report-panel">
      <div className="panel-heading report-heading">
        <div>
          <p className="eyebrow">Advance preparation</p>
          <h2>{pitcherName ? `${pitcherName} advance report` : "Advance report"}</h2>
        </div>
        <span className="result-count">
          {pitches.length} loaded · {totalMatches} matching
        </span>
      </div>

      {!pitches.length ? (
        <div className="empty-state">
          <strong>No report sample available.</strong>
          <span>Select a pitcher or broaden the pitch filters.</span>
        </div>
      ) : (
        <div className="advance-report">
          <section className="report-section arsenal-section">
            <div className="report-section-heading">
              <div>
                <span>01</span>
                <h3>Arsenal overview</h3>
              </div>
              <p>Usage and pitch traits from the current filtered sample.</p>
            </div>
            <div className="report-table-scroll">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Pitch</th>
                    <th>N</th>
                    <th>Usage</th>
                    <th>Velo</th>
                    <th>Spin</th>
                    <th>H-break</th>
                    <th>IVB</th>
                    <th>Whiff/Swing</th>
                    <th>Zone</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.arsenal.map((pitch) => (
                    <tr key={pitch.pitchType}>
                      <td>
                        <span className={`report-pitch-code pitch-${pitch.pitchType.toLowerCase()}`}>
                          {pitch.pitchType}
                        </span>
                        {pitchLabel(pitch.pitchType)}
                      </td>
                      <td>{pitch.count}</td>
                      <td>{formatPercent(pitch.usage)}</td>
                      <td>{formatNumber(pitch.averageVelocity)}</td>
                      <td>{formatNumber(pitch.averageSpin, 0)}</td>
                      <td>{signedBreak(pitch.horizontalBreak)}</td>
                      <td>{signedBreak(pitch.verticalBreak)}</td>
                      <td>{formatPercent(pitch.whiffRate)}</td>
                      <td>{formatPercent(pitch.zoneRate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="report-insight-grid">
            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>02</span><h3>Pitch usage</h3></div>
              </div>
              <strong className="insight-lead">{metrics.usageSummary}</strong>
              <p>{metrics.arsenal.length} pitch types represented in the current sample.</p>
            </section>

            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>03</span><h3>Count tendencies</h3></div>
              </div>
              <dl className="report-list">
                {metrics.countTendencies.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label} <small>n={row.sampleSize}</small></dt>
                    <dd>{row.topPitch} · {formatPercent(row.usage)}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>04</span><h3>Handedness splits</h3></div>
              </div>
              <dl className="report-list">
                {metrics.handedness.map((row) => (
                  <div key={row.side}>
                    <dt>{row.side === "L" ? "vs. LHH" : "vs. RHH"} <small>n={row.count}</small></dt>
                    <dd>{row.topPitch} {formatPercent(row.topPitchUsage)} · Whiff {formatPercent(row.whiffRate)}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>05</span><h3>Location tendencies</h3></div>
              </div>
              <dl className="report-list">
                <div><dt>Zone rate <small>n={metrics.location.sampleSize}</small></dt><dd>{formatPercent(metrics.location.zoneRate)}</dd></div>
                <div><dt>Primary height</dt><dd>{metrics.location.primaryVerticalBand}</dd></div>
                <div><dt>Primary lane</dt><dd>{metrics.location.primaryHorizontalLane}</dd></div>
                <div><dt>Fastballs upper third+</dt><dd>{formatPercent(metrics.location.fastballElevatedRate)}</dd></div>
              </dl>
            </section>

            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>06</span><h3>Putaway approach</h3></div>
              </div>
              <dl className="report-list">
                <div><dt>Two-strike primary <small>n={metrics.putaway.sampleSize}</small></dt><dd>{metrics.putaway.topPitch} · {formatPercent(metrics.putaway.topPitchUsage)}</dd></div>
                <div><dt>Whiff per swing</dt><dd>{formatPercent(metrics.putaway.whiffRate)}</dd></div>
                <div><dt>Best whiff pitch</dt><dd>{metrics.putaway.bestWhiffPitch}</dd></div>
                <div><dt>Recorded strikeouts</dt><dd>{metrics.putaway.strikeouts}</dd></div>
              </dl>
            </section>

            <section className="report-section insight-card">
              <div className="report-section-heading compact-heading">
                <div><span>07</span><h3>Damage allowed</h3></div>
              </div>
              <dl className="report-list">
                <div><dt>Batted balls</dt><dd>{metrics.damage.ballsInPlay}</dd></div>
                <div><dt>Average / maximum EV</dt><dd>{formatNumber(metrics.damage.averageExitVelocity)} / {formatNumber(metrics.damage.maximumExitVelocity)}</dd></div>
                <div><dt>Hard-hit rate (95+)</dt><dd>{formatPercent(metrics.damage.hardHitRate)}</dd></div>
                <div><dt>Highest average-EV pitch</dt><dd>{metrics.damage.mostDamagedPitch} · {metrics.damage.homeRuns} HR</dd></div>
              </dl>
            </section>
          </div>

          <section className="report-section observations-section">
            <div className="report-section-heading">
              <div><span>08</span><h3>Scouting observations</h3></div>
              <p>Your evaluation and context beyond the calculated summaries.</p>
            </div>
            <textarea
              value={observations}
              maxLength={5000}
              rows={7}
              placeholder="Summarize the arsenal, sequencing patterns, command, preferred finish pitches, hitter reactions, and any limitations of the sample…"
              onChange={(event) => setObservations(event.target.value)}
            />
            <small>Browser draft saved automatically · {observations.length}/5,000</small>
          </section>

          <section className="report-section playlist-link-section">
            <div>
              <span className="report-link-label">Supporting video</span>
              <strong>{activePlaylist?.playlist_name ?? "No saved playlist linked"}</strong>
              <p>
                {activePlaylist
                  ? `${activePlaylist.items.length} pitches in PostgreSQL. The link reopens this playlist in the application.`
                  : "Create or open a PostgreSQL playlist to attach a reusable video link."}
              </p>
            </div>
            <div className="report-link-actions">
              {playlistUrl ? (
                <>
                  <a className="primary-button" href={playlistUrl} target="_blank" rel="noreferrer">
                    Open saved video playlist ↗
                  </a>
                  <button className="secondary-button" type="button" onClick={() => void copyPlaylistLink()}>
                    Copy playlist link
                  </button>
                </>
              ) : (
                <button className="primary-button" type="button" disabled>
                  Save a playlist to create a link
                </button>
              )}
              {copyMessage ? <small>{copyMessage}</small> : null}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
