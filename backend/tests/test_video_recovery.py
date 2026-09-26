"""Recovery only exports links whose original pitch identities now match."""

import csv

from scripts.recover_video_links import recover

PLAY_ID = "b7cbd5a2-f23f-34e1-bb4e-1c441da2f3b4"


def row():
    return {"pitch_id": "824566_8_1", "game_pk": "824566",
            "game_date": "2026-08-07", "at_bat_number": "8", "pitch_number": "1",
            "pitcher": "800048", "batter": "700001", "inning": "1", "inning_topbot": "Top"}


def feed():
    return {"gamePk": 824566,
            "gameData": {"datetime": {"originalDate": "2026-08-07"}},
            "liveData": {"plays": {"allPlays": [{
                "about": {"atBatIndex": 7, "inning": 1, "halfInning": "top"},
                "matchup": {"pitcher": {"id": 800048}, "batter": {"id": 700001}},
                "playEvents": [{"isPitch": True, "pitchNumber": 1, "playId": PLAY_ID}],
            }]}}}


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_recover_exact_match_and_keep_wrong_player_for_review(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    source = row()
    second = {**row(), "pitch_id": "824566_8_2", "pitch_number": "2"}
    write_csv(raw / "statcast_2026-08-07.csv", [source, second])
    report = tmp_path / "video_match_report.csv"
    write_csv(report, [
        {**source, "status": "review", "reason": "no_pitch_event", "play_id": ""},
        {**second, "status": "review", "reason": "player_id_mismatch", "play_id": ""},
    ])
    current = feed()
    # The wrong player's event must never become an importable link.
    current["liveData"]["plays"]["allPlays"].append({
        "about": {"atBatIndex": 7, "inning": 1, "halfInning": "top"},
        "matchup": {"pitcher": {"id": 999999}, "batter": {"id": 700001}},
        "playEvents": [{"isPitch": True, "pitchNumber": 2,
                        "playId": "638ea166-569e-4cad-ab09-9065b3e10101"}],
    })
    counts = recover(report, raw, tmp_path / "cache", tmp_path / "out", delay=0,
                     fetcher=lambda *args, **kwargs: current)
    assert counts["recovered"] == 1
    assert len(read_csv(tmp_path / "out" / "recovered_links.csv")) == 1
    assert read_csv(tmp_path / "out" / "recovered_links.csv")[0]["pitch_id"] == source["pitch_id"]
    assert read_csv(tmp_path / "out" / "still_needs_review.csv")[0]["pitch_id"] == second["pitch_id"]


def test_recovery_rejects_play_id_already_used(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    source = row()
    write_csv(raw / "statcast_2026-08-07.csv", [source])
    report = tmp_path / "video_match_report.csv"
    write_csv(report, [
        {**source, "pitch_id": "824566_8_2", "status": "matched",
         "reason": "", "play_id": PLAY_ID},
        {**source, "status": "review", "reason": "no_pitch_event", "play_id": ""},
    ])
    counts = recover(report, raw, tmp_path / "cache", tmp_path / "out", delay=0,
                     fetcher=lambda *args, **kwargs: feed())
    assert counts["review:play_id_already_matched"] == 1
    assert read_csv(tmp_path / "out" / "recovered_links.csv") == []
