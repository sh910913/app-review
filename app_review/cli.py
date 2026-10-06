from __future__ import annotations

import argparse
import csv
import json
import sys

from app_review.countries import STOREFRONTS
from app_review.itunes import ItunesError
from app_review.service import SORTS, load_reviews


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download public App Store reviews for every country storefront. "
            "No developer account is required."
        )
    )
    parser.add_argument("app", help="App Store URL or numeric app id")
    parser.add_argument(
        "--countries",
        help="Comma-separated storefront codes. Default: scan every storefront.",
    )
    parser.add_argument(
        "--sort",
        choices=SORTS,
        default="mostrecent",
        help="Review order inside each storefront (default: mostrecent)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--out", help="Write to this file instead of stdout")
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel requests (default: 8)",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        print("--workers must be at least 1", file=sys.stderr)
        return 1

    try:
        countries = _countries(args.countries)
        payload = load_reviews(
            args.app,
            countries=countries,
            sort=args.sort,
            workers=args.workers,
            on_status=_print_status,
        )
    except ItunesError as error:
        print(error, file=sys.stderr)
        return 1

    _write(args.format, args.out, payload)
    reviews = payload["reviews"]
    count = len(reviews) if isinstance(reviews, list) else 0
    print(f"Wrote {count} reviews.", file=sys.stderr)
    return 0


def _countries(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    codes = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    if not codes:
        raise ItunesError("--countries needs at least one storefront code")
    unknown = [code for code in codes if code not in STOREFRONTS]
    if unknown:
        raise ItunesError("Unknown storefront code: " + ", ".join(unknown))
    return codes


def _print_status(event: dict[str, object]) -> None:
    kind = event.get("kind")
    if kind == "scan":
        print(
            f"Scanning {event['count']} storefronts for {event['app_id']}...",
            file=sys.stderr,
        )
    elif kind == "failure":
        print(event["message"], file=sys.stderr)
    elif kind == "empty":
        print(
            f"{event['name']} has no ratings in the scanned storefronts.",
            file=sys.stderr,
        )
    elif kind == "ratings":
        storefronts = event["storefronts"]
        if isinstance(storefronts, list):
            parts = [
                f"{item['country']}={item['rating_count']}"
                for item in storefronts
                if isinstance(item, dict)
            ]
            print("Ratings: " + ", ".join(parts), file=sys.stderr)
    elif kind == "fetched":
        note = " (stopped at Apple's 500-review cap)" if event.get("truncated") else ""
        print(
            f"{event['country']}: {event['review_count']} written reviews{note}",
            file=sys.stderr,
        )


def _write(fmt: str, path: str | None, payload: dict[str, object]) -> None:
    if fmt == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        _emit(path, text)
        return

    reviews = payload["reviews"]
    if not isinstance(reviews, list):
        reviews = []
    fieldnames = [
        "country",
        "id",
        "rating",
        "title",
        "author",
        "content",
        "version",
        "updated",
        "vote_count",
        "vote_sum",
    ]
    if path:
        handle = open(path, "w", encoding="utf-8-sig", newline="")
    else:
        handle = sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for review in reviews:
            if isinstance(review, dict):
                writer.writerow(review)
    finally:
        if path:
            handle.close()


def _emit(path: str | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
