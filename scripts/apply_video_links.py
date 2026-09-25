#!/usr/bin/env python3
"""Validate and load official pitch-page links into a selected PostgreSQL database."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import psycopg

from scripts.match_official_videos import VIDEO_URL, MatchError, positive_int


def read_links(path: Path) -> list[dict[str, object]]:
    """Reject duplicate keys, untrusted URLs and incomplete player identities."""
    links: list[dict[str, object]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"pitch_id", "game_pk", "pitcher", "batter", "video_url"}
        if required - set(reader.fieldnames or []):
            raise MatchError("Link file needs pitch_id, game_pk, pitcher, batter and video_url")
        for number, row in enumerate(reader, start=2):
            try:
                game, pitcher, batter = (
                    positive_int(row[name]) for name in ("game_pk", "pitcher", "batter")
                )
                pitch_id = row["pitch_id"].strip()
                parts = pitch_id.split("_")
                if len(parts) != 3 or any(positive_int(part) < 1 for part in parts):
                    raise ValueError("invalid pitch ID")
                if int(parts[0]) != game or pitch_id in seen:
                    raise ValueError("duplicate or inconsistent pitch ID")
                parsed = urlparse(row["video_url"].strip())
                ids = parse_qs(parsed.query).get("playId", [])
                if (
                    parsed.scheme != "https"
                    or parsed.netloc != "baseballsavant.mlb.com"
                    or parsed.path != "/sporty-videos"
                    or len(ids) != 1
                ):
                    raise ValueError("not an official Savant pitch page")
                play_id = str(UUID(ids[0]))
                if row["video_url"].strip() != VIDEO_URL.format(play_id=play_id):
                    raise ValueError("noncanonical official page URL")
            except (ValueError, TypeError, KeyError) as exc:
                raise MatchError(
                    f"{path.name}:{number}: invalid or duplicate link identity"
                ) from exc
            seen.add(pitch_id)
            links.append(
                {
                    "pitch_id": pitch_id,
                    "game_pk": game,
                    "pitcher": pitcher,
                    "batter": batter,
                    "video_url": row["video_url"].strip(),
                }
            )
    if not links:
        raise MatchError("No matched links in file")
    return links


def apply_links(
    connection: psycopg.Connection, links: list[dict[str, object]], *, apply: bool
) -> tuple[int, int]:
    """Match every source pitch to DB identities in one transaction; keep existing URLs."""
    ids = [link["pitch_id"] for link in links]
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.pitch_id, p.game_pk, pitcher.mlb_id, batter.mlb_id,
                   v.pitch_id AS existing_video
            FROM pitches AS p
            JOIN players AS pitcher ON pitcher.player_id = p.pitcher_id
            JOIN players AS batter ON batter.player_id = p.batter_id
            LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
            WHERE p.pitch_id = ANY(%s)
            """,
            (ids,),
        )
        found = {row[0]: row[1:] for row in cursor.fetchall()}
        if len(found) != len(links):
            raise MatchError(f"{len(links) - len(found)} pitch IDs do not exist in this database")
        for link in links:
            game, pitcher, batter, _ = found[link["pitch_id"]]
            if (game, pitcher, batter) != (link["game_pk"], link["pitcher"], link["batter"]):
                raise MatchError(f"Database identity differs for {link['pitch_id']}")
        new_links = [link for link in links if found[link["pitch_id"]][3] is None]
        if apply and new_links:
            cursor.executemany(
                """
                INSERT INTO videos (pitch_id, video_url, video_type, video_available, notes)
                VALUES (%(pitch_id)s, %(video_url)s, 'Pitch', TRUE,
                        'Official Savant pitch page matched to MLB game feed')
                ON CONFLICT (pitch_id) DO NOTHING
                """,
                new_links,
            )
        return len(new_links), len(links) - len(new_links)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--expected-host", required=True, help="Private Neon endpoint hostname")
    parser.add_argument("--expected-database", default="baseball_video_scouting")
    parser.add_argument(
        "--apply", action="store_true", help="Write links after a successful dry run"
    )
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        parser.error("Set DATABASE_URL for the private database in this terminal")
    try:
        host = urlparse(url).hostname
        if host != args.expected_host or "-pooler" not in host or not host.endswith(".neon.tech"):
            raise MatchError("Database endpoint differs from --expected-host")
        links = read_links(args.links)
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != args.expected_database:
                    raise MatchError("Database name differs from --expected-database")
            new, existing = apply_links(connection, links, apply=args.apply)
    except (MatchError, OSError, psycopg.Error) as exc:
        # Driver exceptions can contain the URL; never print them.
        print(f"Video link import stopped: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Validated: {len(links):,}; new: {new:,}; already linked: {existing:,}")
    print("Applied new links." if args.apply else "Dry run only; use --apply to insert new links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
