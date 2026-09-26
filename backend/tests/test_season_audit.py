"""Cover source/DB reconciliation and intentional preservation of curated links."""

import csv
from datetime import date

import pytest

from scripts.audit_private_season import AuditError, audit_reports, load_report

START = date(2026, 8, 1)
END = date(2026, 8, 31)
FIELDS = ("pitch_id", "game_date", "game_pk", "pitcher", "batter", "status", "reason", "video_url")
MATCH_URL = (
    "https://baseballsavant.mlb.com/sporty-videos?playId=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
)
CURATED_URL = (
    "https://baseballsavant.mlb.com/sporty-videos?playId=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
)


def write_report(tmp_path, rows):
    path = tmp_path / f"{START}_{END}" / "video_match_report.csv"
    path.parent.mkdir()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


class FakeCursor:
    def __init__(self, count, stored_url):
        self.count = count
        self.stored_url = stored_url
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, parameters):
        self.query = query
        if "BETWEEN" in query:
            assert parameters == (START, END)
        else:
            assert parameters == (["822684_1_1"],)

    def fetchone(self):
        return {"pitches": self.count, "linked": self.count}

    def fetchall(self):
        return [
            {
                "pitch_id": "822684_1_1",
                "game_pk": 822684,
                "game_date": START,
                "pitcher": 11,
                "batter": 12,
                "video_url": self.stored_url,
                "video_available": True,
            }
        ]


class FakeConnection:
    def __init__(self, count=1, stored_url=MATCH_URL):
        self.count = count
        self.stored_url = stored_url

    def cursor(self):
        return FakeCursor(self.count, self.stored_url)


def sample_row():
    return {
        "pitch_id": "822684_1_1",
        "game_date": START.isoformat(),
        "game_pk": "822684",
        "pitcher": "11",
        "batter": "12",
        "status": "matched",
        "reason": "",
        "video_url": MATCH_URL,
    }


def test_duplicate_source_pitch_rejected(tmp_path):
    path = write_report(tmp_path, [sample_row(), sample_row()])
    with pytest.raises(AuditError, match="Duplicate pitch"):
        load_report(path, START, END)


def test_report_count_must_equal_database_count(tmp_path):
    write_report(tmp_path, [sample_row()])
    with pytest.raises(AuditError, match="report has 1 rows, database has 2"):
        audit_reports(FakeConnection(count=2), tmp_path, [(START, END)], 1)


def test_curated_video_link_is_reported_without_failing_valid_identity(tmp_path, capsys):
    write_report(tmp_path, [sample_row()])
    assert audit_reports(FakeConnection(stored_url=CURATED_URL), tmp_path, [(START, END)], 1) == 1
    output = capsys.readouterr().out
    assert "1 existing video URL(s) differ" in output
    assert MATCH_URL in output and CURATED_URL in output
