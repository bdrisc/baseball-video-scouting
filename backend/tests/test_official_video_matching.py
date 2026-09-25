"""Verify pitch-level identity checks, review output and safe import behavior."""

import csv
from contextlib import nullcontext
from datetime import date

import pytest

from scripts.apply_video_links import apply_links, read_links
from scripts.match_official_videos import MatchError, match_pitch, pitch_rows, run

PLAY_ID = "b7cbd5a2-f23f-34e1-bb4e-1c441da2f3b4"


def feed(*, pitcher=800048, batter=700001, play_id=PLAY_ID):
    return {
        "gamePk": 824566,
        "gameData": {"datetime": {"originalDate": "2026-08-07"}},
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 7, "inning": 1, "halfInning": "top"},
                        "matchup": {"pitcher": {"id": pitcher}, "batter": {"id": batter}},
                        "playEvents": [
                            {"isPitch": False, "pitchNumber": 1, "playId": "other"},
                            {"isPitch": True, "pitchNumber": 1, "playId": play_id},
                        ],
                    }
                ]
            }
        },
    }


def row():
    return {
        "pitch_id": "824566_8_1",
        "game_pk": "824566",
        "game_date": "2026-08-07",
        "at_bat_number": "8",
        "pitch_number": "1",
        "pitcher": "800048",
        "batter": "700001",
        "inning": "1",
        "inning_topbot": "Top",
    }


def test_exact_pitch_match_and_identity_mismatches():
    from scripts.match_official_videos import index_feed

    matched = match_pitch(row(), index_feed(feed()))
    assert matched["status"] == "matched"
    assert matched["video_url"] == f"https://baseballsavant.mlb.com/sporty-videos?playId={PLAY_ID}"
    assert match_pitch(row(), index_feed(feed(pitcher=42)))["reason"] == "player_id_mismatch"
    assert match_pitch(row(), index_feed(feed(play_id="")))["reason"] == "missing_play_id"
    assert match_pitch(row(), {})["reason"] == "no_pitch_event"
    wrong_half = {**row(), "inning_topbot": "Bot"}
    assert match_pitch(wrong_half, index_feed(feed()))["reason"] == "inning_half_mismatch"


def test_month_run_exports_only_high_confidence_links(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    source = raw / "statcast_2026-08-07.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*row(), "extra"])
        writer.writeheader()
        writer.writerow({**row(), "extra": "ignored"})
        writer.writerow({**row(), "pitch_number": "2", "extra": "ignored"})
    output = tmp_path / "processed"
    counts = run(
        raw,
        date(2026, 8, 1),
        date(2026, 8, 31),
        output,
        tmp_path / "cache",
        delay=0,
        fetcher=lambda *args, **kwargs: feed(),
    )
    assert counts == {"matched": 1, "no_pitch_event": 1}
    with (output / "video_links_matched.csv").open() as handle:
        links = list(csv.DictReader(handle))
    assert len(links) == 1
    assert links[0]["pitch_id"] == "824566_8_1"
    assert len(read_links(output / "video_links_matched.csv")) == 1


def test_duplicate_official_play_id_requires_review(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    with (raw / "statcast_day.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row()))
        writer.writeheader()
        writer.writerow(row())
        writer.writerow({**row(), "pitch_number": "2"})
    duplicate_feed = feed()
    duplicate_feed["liveData"]["plays"]["allPlays"][0]["playEvents"].append(
        {"isPitch": True, "pitchNumber": 2, "playId": PLAY_ID}
    )
    output = tmp_path / "output"
    counts = run(
        raw,
        date(2026, 8, 1),
        date(2026, 8, 31),
        output,
        tmp_path / "cache",
        delay=0,
        fetcher=lambda *args, **kwargs: duplicate_feed,
    )
    assert counts == {"duplicate_play_id": 2}
    with (output / "video_links_matched.csv").open() as handle:
        assert list(csv.DictReader(handle)) == []


def test_conflicting_source_and_untrusted_links_are_rejected(tmp_path):
    source = tmp_path / "pitches.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row()))
        writer.writeheader()
        writer.writerow(row())
        writer.writerow({**row(), "batter": "123"})
    with pytest.raises(MatchError, match="Conflicting source"):
        pitch_rows([source], date(2026, 8, 1), date(2026, 8, 31))
    links = tmp_path / "links.csv"
    with links.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["pitch_id", "game_pk", "pitcher", "batter", "video_url"]
        )
        writer.writeheader()
        writer.writerow(
            {
                **{name: row()[name] for name in ("pitch_id", "game_pk", "pitcher", "batter")},
                "video_url": f"https://example.com/sporty-videos?playId={PLAY_ID}",
            }
        )
    with pytest.raises(MatchError, match="invalid or duplicate"):
        read_links(links)


def test_import_verifies_every_identity_and_keeps_existing_links():
    class FakeConnection:
        def __init__(self, rows):
            self.rows = rows
            self.inserted = []

        def transaction(self):
            return nullcontext()

        def cursor(self):
            return nullcontext(self)

        def execute(self, query, parameters):
            assert "WHERE p.pitch_id = ANY" in query
            assert parameters == (["824566_8_1"],)

        def fetchall(self):
            return self.rows

        def executemany(self, query, parameters):
            self.inserted.extend(parameters)

    link = {
        "pitch_id": "824566_8_1",
        "game_pk": 824566,
        "pitcher": 800048,
        "batter": 700001,
        "video_url": "official link",
    }
    connection = FakeConnection([("824566_8_1", 824566, 800048, 700001, None)])
    assert apply_links(connection, [link], apply=False) == (1, 0)
    assert connection.inserted == []
    assert apply_links(connection, [link], apply=True) == (1, 0)
    assert connection.inserted == [link]
    connection.rows = [("824566_8_1", 824566, 800048, 700001, "824566_8_1")]
    assert apply_links(connection, [link], apply=True) == (0, 1)
    assert connection.inserted == [link]
    connection.rows = [("824566_8_1", 824566, 111, 700001, None)]
    with pytest.raises(MatchError, match="Database identity differs"):
        apply_links(connection, [link], apply=True)
    assert connection.inserted == [link]
