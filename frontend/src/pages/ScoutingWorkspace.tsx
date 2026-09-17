import { useEffect, useState } from "react";

import FilterPanel from "../components/FilterPanel";
import GameSelector from "../components/GameSelector";
import MovementPlot from "../components/MovementPlot";
import PitchDetails from "../components/PitchDetails";
import PitcherSelector from "../components/PitcherSelector";
import PitchTable from "../components/PitchTable";
import PitchUsageChart from "../components/PitchUsageChart";
import PlaylistBuilder from "../components/PlaylistBuilder";
import ResultsByBatterSideChart from "../components/ResultsByBatterSideChart";
import ScoutingReport from "../components/ScoutingReport";
import ScopeSelectors from "../components/ScopeSelectors";
import StrikeZonePlot from "../components/StrikeZonePlot";
import SummaryStats from "../components/SummaryStats";
import UsageByCountChart from "../components/UsageByCountChart";
import VelocityByInningChart from "../components/VelocityByInningChart";
import VideoPanel from "../components/VideoPanel";
import useDebouncedValue from "../hooks/useDebouncedValue";
import {
  API_BASE_URL,
  getHealth,
  getPitchAggregates,
  getPitcherGames,
  getPitches,
  getSeasons,
  getTeams,
  READ_ONLY_MODE,
  searchPitchers,
} from "../services/api";
import type {
  Game,
  HealthResponse,
  Pitch,
  PitchAggregateResponse,
  Pitcher,
  PitchSearchFilters,
  PitchSortField,
  PlaylistDetail,
  SeasonSummary,
  SortOrder,
  TeamSummary,
} from "../types/api";

type EditableFilters = Omit<
  PitchSearchFilters,
  | "pitcher_id"
  | "game_pk"
  | "season"
  | "team_id"
  | "limit"
  | "offset"
  | "sort_by"
  | "sort_order"
>;

const DEFAULT_PAGE_SIZE = 500;

const defaultFilters: EditableFilters = {
  batter_side: "",
  pitch_type: "",
  balls: null,
  strikes: null,
  result: "",
  min_velocity: null,
  max_velocity: null,
  min_plate_x: null,
  max_plate_x: null,
  min_plate_z: null,
  max_plate_z: null,
  video_available: null,
};

export default function ScoutingWorkspace() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [pitchers, setPitchers] = useState<Pitcher[]>([]);
  const [pitcherTotal, setPitcherTotal] = useState(0);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [pitcherQuery, setPitcherQuery] = useState("");
  const debouncedPitcherQuery = useDebouncedValue(pitcherQuery, 300);
  const [selectedPitcher, setSelectedPitcher] = useState<Pitcher | null>(null);
  const selectedPitcherId = selectedPitcher?.player_id ?? null;
  const [games, setGames] = useState<Game[]>([]);
  const [pitches, setPitches] = useState<Pitch[]>([]);
  const [aggregates, setAggregates] = useState<PitchAggregateResponse | null>(
    null,
  );
  const [totalMatches, setTotalMatches] = useState(0);
  const [pageLimit, setPageLimit] = useState(DEFAULT_PAGE_SIZE);
  const [pageOffset, setPageOffset] = useState(0);
  const [sortBy, setSortBy] = useState<PitchSortField>("game_date");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [filters, setFilters] = useState<EditableFilters>(defaultFilters);
  const debouncedFilters = useDebouncedValue(filters, 300);
  const [stagedPitches, setStagedPitches] = useState<Pitch[]>([]);
  const [selectedGamePk, setSelectedGamePk] = useState<number | null>(null);
  const [selectedPitch, setSelectedPitch] = useState<Pitch | null>(null);
  const [scoutingNotes, setScoutingNotes] = useState<Record<string, string>>({});
  const [playlistReviewActive, setPlaylistReviewActive] = useState(false);
  const [activePlaylist, setActivePlaylist] = useState<PlaylistDetail | null>(null);
  const [initialPlaylistId] = useState<number | null>(() => {
    const value = Number(new URLSearchParams(window.location.search).get("playlist"));
    return Number.isInteger(value) && value > 0 ? value : null;
  });
  const [initialLoading, setInitialLoading] = useState(true);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [pitcherSearchLoading, setPitcherSearchLoading] = useState(false);
  const [gamesLoading, setGamesLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [aggregateLoading, setAggregateLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [aggregateError, setAggregateError] = useState<string | null>(null);
  const [pitcherSearchError, setPitcherSearchError] = useState<string | null>(null);

  useEffect(() => {
    setPageOffset(0);
  }, [
    debouncedFilters,
    selectedGamePk,
    selectedPitcherId,
    selectedSeason,
    selectedTeamId,
  ]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadInitialData() {
      setInitialLoading(true);
      setError(null);

      try {
        const [healthResponse, seasonResponse] = await Promise.all([
          getHealth(controller.signal),
          getSeasons(controller.signal),
        ]);
        setHealth(healthResponse);
        setSeasons(seasonResponse);
        setSelectedSeason(seasonResponse[0]?.season ?? null);
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not reach the FastAPI backend.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setInitialLoading(false);
        }
      }
    }

    void loadInitialData();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadTeams() {
      setScopeLoading(true);
      try {
        setTeams(await getTeams(selectedSeason, controller.signal));
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load teams.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setScopeLoading(false);
      }
    }

    void loadTeams();
    return () => controller.abort();
  }, [selectedSeason]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadPitchers() {
      setPitcherSearchLoading(true);
      setPitcherSearchError(null);
      try {
        const response = await searchPitchers(
          {
            q: debouncedPitcherQuery,
            season: selectedSeason,
            team_id: selectedTeamId,
            throws: "",
            limit: 50,
            offset: 0,
          },
          controller.signal,
        );
        setPitchers(response.pitchers);
        setPitcherTotal(response.total);
        setSelectedPitcher((currentPitcher) =>
          response.total === 1 && currentPitcher === null
            ? response.pitchers[0]
            : currentPitcher,
        );
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setPitcherSearchError(
            requestError instanceof Error
              ? requestError.message
              : "Could not search pitchers.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setPitcherSearchLoading(false);
      }
    }

    void loadPitchers();
    return () => controller.abort();
  }, [debouncedPitcherQuery, selectedSeason, selectedTeamId]);

  useEffect(() => {
    const controller = new AbortController();

    if (selectedPitcherId === null) {
      setGames([]);
      setSelectedGamePk(null);
      return () => controller.abort();
    }

    async function loadGames() {
      setGamesLoading(true);
      setSelectedGamePk(null);
      setSelectedPitch(null);

      try {
        const response = await getPitcherGames(
          selectedPitcherId as number,
          { season: selectedSeason, team_id: selectedTeamId },
          controller.signal,
        );
        setGames(response.games);
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load games.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setGamesLoading(false);
        }
      }
    }

    void loadGames();
    return () => controller.abort();
  }, [selectedPitcherId, selectedSeason, selectedTeamId]);

  useEffect(() => {
    const controller = new AbortController();

    if (selectedPitcherId === null) {
      setPitches([]);
      setTotalMatches(0);
      return () => controller.abort();
    }

    async function loadPitches() {
      setSearchLoading(true);
      setSearchError(null);

      try {
        const response = await getPitches(
          {
            pitcher_id: selectedPitcherId as number,
            game_pk: selectedGamePk,
            season: selectedSeason,
            team_id: selectedTeamId,
            ...debouncedFilters,
            limit: pageLimit,
            offset: pageOffset,
            sort_by: sortBy,
            sort_order: sortOrder,
          },
          controller.signal,
        );
        setPitches(response.pitches);
        setTotalMatches(response.total);
        setSelectedPitch((currentPitch) => {
          if (!currentPitch) return null;
          return (
            response.pitches.find(
              (pitch) => pitch.pitch_id === currentPitch.pitch_id,
            ) ?? null
          );
        });
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setSearchError(
            requestError instanceof Error
              ? requestError.message
              : "Could not search pitches.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setSearchLoading(false);
        }
      }
    }

    void loadPitches();
    return () => controller.abort();
  }, [
    debouncedFilters,
    pageLimit,
    pageOffset,
    selectedGamePk,
    selectedPitcherId,
    selectedSeason,
    selectedTeamId,
    sortBy,
    sortOrder,
  ]);

  useEffect(() => {
    const controller = new AbortController();

    if (selectedPitcherId === null) {
      setAggregates(null);
      return () => controller.abort();
    }

    async function loadAggregates() {
      setAggregateLoading(true);
      setAggregateError(null);
      setAggregates(null);

      try {
        const response = await getPitchAggregates(
          {
            pitcher_id: selectedPitcherId as number,
            game_pk: selectedGamePk,
            season: selectedSeason,
            team_id: selectedTeamId,
            ...debouncedFilters,
          },
          controller.signal,
        );
        setAggregates(response);
      } catch (requestError) {
        if (!controller.signal.aborted) {
          setAggregateError(
            requestError instanceof Error
              ? requestError.message
              : "Could not calculate full-result summaries.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setAggregateLoading(false);
        }
      }
    }

    void loadAggregates();
    return () => controller.abort();
  }, [
    debouncedFilters,
    selectedGamePk,
    selectedPitcherId,
    selectedSeason,
    selectedTeamId,
  ]);

  function handlePitcherChange(pitcher: Pitcher | null) {
    setSelectedPitcher(pitcher);
    setSelectedGamePk(null);
    setSelectedPitch(null);
    setFilters(defaultFilters);
    setPageOffset(0);
  }

  function handleSeasonChange(season: number | null) {
    setSelectedSeason(season);
    setSelectedTeamId(null);
    setSelectedPitcher(null);
    setPitcherQuery("");
    setSelectedGamePk(null);
    setSelectedPitch(null);
  }

  function handleTeamChange(teamId: number | null) {
    setSelectedTeamId(teamId);
    setSelectedPitcher(null);
    setPitcherQuery("");
    setSelectedGamePk(null);
    setSelectedPitch(null);
  }

  function handleGameChange(gamePk: number | null) {
    setSelectedGamePk(gamePk);
    setSelectedPitch(null);
    setPageOffset(0);
  }

  function resetFilters() {
    setFilters(defaultFilters);
    setSelectedGamePk(null);
    setSelectedPitch(null);
    setPageOffset(0);
  }

  function stagePitch(pitch: Pitch) {
    setSelectedPitch(pitch);
    setStagedPitches((current) =>
      current.some((item) => item.pitch_id === pitch.pitch_id)
        ? current
        : [...current, pitch],
    );
  }

  function updateScoutingNote(pitchId: string, note: string) {
    setScoutingNotes((current) => ({ ...current, [pitchId]: note }));
  }

  function moveStagedPitch(pitchId: string, direction: "up" | "down") {
    setStagedPitches((current) => {
      const currentIndex = current.findIndex(
        (pitch) => pitch.pitch_id === pitchId,
      );
      const destinationIndex =
        direction === "up" ? currentIndex - 1 : currentIndex + 1;
      if (
        currentIndex < 0 ||
        destinationIndex < 0 ||
        destinationIndex >= current.length
      ) {
        return current;
      }

      const reordered = [...current];
      [reordered[currentIndex], reordered[destinationIndex]] = [
        reordered[destinationIndex],
        reordered[currentIndex],
      ];
      return reordered;
    });
  }

  function loadSavedPlaylist(playlist: PlaylistDetail | null) {
    setActivePlaylist(playlist);
    const url = new URL(window.location.href);
    if (playlist) url.searchParams.set("playlist", String(playlist.playlist_id));
    else url.searchParams.delete("playlist");
    window.history.replaceState({}, "", url);

    if (!playlist) return;
    setStagedPitches(playlist.items);
    setScoutingNotes((current) => ({
      ...current,
      ...Object.fromEntries(
        playlist.items.map((item) => [item.pitch_id, item.scouting_note ?? ""]),
      ),
    }));
    setPlaylistReviewActive(false);
    setSelectedPitch(playlist.items[0] ?? null);
  }

  function startPlaylistReview() {
    const firstVideoPitch = stagedPitches.find(
      (pitch) => pitch.video_available && pitch.video_url,
    );
    if (!firstVideoPitch) return;
    setPlaylistReviewActive(true);
    selectPitchAndReveal(firstVideoPitch);
  }

  function selectPitchAndReveal(pitch: Pitch) {
    setSelectedPitch(pitch);
    window.requestAnimationFrame(() => {
      document
        .getElementById(`pitch-row-${pitch.pitch_id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="brand-kicker">BASEBALL OPERATIONS</p>
          <h1>Video Scouting Workspace</h1>
        </div>
        <div
          className={`connection-badge ${health ? "connected" : "disconnected"}`}
        >
          <span className="status-dot" />
          {initialLoading
            ? "Checking API"
            : health
              ? `Connected · ${health.database}`
              : "Backend unavailable"}
        </div>
      </header>

      <main>
        <section className="workspace-intro">
          <div>
            <p className="eyebrow">Step 20 · Advance report</p>
            <h2>
              {selectedPitcher?.player_name ?? "Select a pitcher to begin"}
            </h2>
            <p>
              Search pitch-level data, review official video, organize
              playlists, and build an advance report from one workflow.
            </p>
          </div>
          <div className="api-address">
            <span>API</span>
            <code>{API_BASE_URL}</code>
          </div>
        </section>

        {error ? (
          <div className="error-banner" role="alert">
            <strong>Could not load backend data.</strong>
            <span>{error}</span>
          </div>
        ) : null}

        {pitcherSearchError ? (
          <div className="error-banner" role="alert">
            <strong>Pitcher search failed.</strong>
            <span>{pitcherSearchError}</span>
          </div>
        ) : null}

        <section className="selector-bar">
          <ScopeSelectors
            seasons={seasons}
            teams={teams}
            selectedSeason={selectedSeason}
            selectedTeamId={selectedTeamId}
            loading={initialLoading || scopeLoading}
            onSeasonChange={handleSeasonChange}
            onTeamChange={handleTeamChange}
          />
          <PitcherSelector
            pitchers={pitchers}
            selectedPitcher={selectedPitcher}
            query={pitcherQuery}
            total={pitcherTotal}
            loading={initialLoading || pitcherSearchLoading}
            onQueryChange={setPitcherQuery}
            onChange={handlePitcherChange}
          />
          <GameSelector
            games={games}
            selectedGamePk={selectedGamePk}
            disabled={selectedPitcherId === null}
            loading={gamesLoading}
            onChange={handleGameChange}
          />
          <div className="selection-summary">
            <span>Current result</span>
            <strong>{searchLoading ? "Searching…" : `${totalMatches} pitches`}</strong>
          </div>
        </section>

        <div className="workspace-grid">
          <aside className="sidebar-stack">
            <FilterPanel
              filters={filters}
              disabled={selectedPitcherId === null}
              onChange={setFilters}
              onReset={resetFilters}
            />
            <PlaylistBuilder
              readOnly={READ_ONLY_MODE}
              stagedPitches={stagedPitches}
              scoutingNotes={scoutingNotes}
              onScoutingNoteChange={updateScoutingNote}
              onSelectPitch={selectPitchAndReveal}
              onMove={moveStagedPitch}
              onRemove={(pitchId) =>
                setStagedPitches((current) =>
                  current.filter((pitch) => pitch.pitch_id !== pitchId),
                )
              }
              onClear={() => {
                setStagedPitches([]);
                setPlaylistReviewActive(false);
              }}
              initialPlaylistId={initialPlaylistId}
              onLoadPlaylist={loadSavedPlaylist}
              onStartReview={startPlaylistReview}
            />
          </aside>

          <div className="content-stack">
            {searchError ? (
              <div className="error-banner" role="alert">
                <strong>Pitch search failed.</strong>
                <span>{searchError}</span>
              </div>
            ) : null}

            {aggregateError ? (
              <div className="error-banner" role="alert">
                <strong>Full-result summaries failed.</strong>
                <span>{aggregateError}</span>
              </div>
            ) : null}

            <SummaryStats
              summary={aggregates?.summary ?? null}
              loading={aggregateLoading}
            />

            <PitchTable
              pitches={pitches}
              totalMatches={totalMatches}
              limit={pageLimit}
              offset={pageOffset}
              sortBy={sortBy}
              sortOrder={sortOrder}
              loading={searchLoading}
              selectedPitchId={selectedPitch?.pitch_id ?? null}
              stagedPitchIds={stagedPitches.map((pitch) => pitch.pitch_id)}
              onSelect={setSelectedPitch}
              onAddToPlaylist={stagePitch}
              onPageChange={setPageOffset}
              onPageSizeChange={(limit) => {
                setPageLimit(limit);
                setPageOffset(0);
              }}
              onSortChange={(field, order) => {
                setSortBy(field);
                setSortOrder(order);
                setPageOffset(0);
              }}
            />

            <div className="two-column-grid">
              <PitchDetails
                pitch={selectedPitch}
                scoutingNote={
                  selectedPitch ? scoutingNotes[selectedPitch.pitch_id] ?? "" : ""
                }
                onScoutingNoteChange={(note) => {
                  if (!selectedPitch) return;
                  updateScoutingNote(selectedPitch.pitch_id, note);
                }}
              />
              <VideoPanel
                pitch={selectedPitch}
                pitches={playlistReviewActive ? stagedPitches : pitches}
                stagedPitchIds={stagedPitches.map((pitch) => pitch.pitch_id)}
                onSelect={selectPitchAndReveal}
                onAddToPlaylist={stagePitch}
                playlistReviewActive={playlistReviewActive}
                onExitPlaylistReview={() => setPlaylistReviewActive(false)}
              />
            </div>

            <div className="two-column-grid">
              <StrikeZonePlot
                pitches={pitches}
                selectedPitchId={selectedPitch?.pitch_id ?? null}
                onSelect={selectPitchAndReveal}
              />
              <MovementPlot
                pitches={pitches}
                selectedPitchId={selectedPitch?.pitch_id ?? null}
                onSelect={selectPitchAndReveal}
              />
            </div>

            {aggregates ? (
              <>
                <div className="two-column-grid">
                  <PitchUsageChart rows={aggregates.pitch_usage} />
                  <VelocityByInningChart
                    rows={aggregates.velocity_by_inning}
                  />
                </div>

                <div className="two-column-grid">
                  <UsageByCountChart rows={aggregates.usage_by_count} />
                  <ResultsByBatterSideChart
                    rows={aggregates.results_by_batter_side}
                  />
                </div>

                <ScoutingReport
                  metrics={aggregates.report}
                  totalMatches={aggregates.total}
                  pitcherId={selectedPitcherId}
                  pitcherName={selectedPitcher?.player_name ?? null}
                  activePlaylist={activePlaylist}
                />
              </>
            ) : aggregateLoading ? (
              <section className="panel">
                <div className="empty-state" role="status">
                  <strong>Calculating full-result summaries…</strong>
                  <span>
                    PostgreSQL is aggregating every pitch that matches the
                    current filters.
                  </span>
                </div>
              </section>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
