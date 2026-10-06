"""Collect public reviews for one app across storefronts."""

from __future__ import annotations

from collections.abc import Callable

from app_review.countries import STOREFRONTS
from app_review.itunes import (
    AppNotFound,
    CountryReviews,
    ItunesError,
    Review,
    Storefront,
    fetch_storefront_reviews,
    lookup_metadata,
    parse_app_id,
    scan_storefronts,
)

StatusCallback = Callable[[dict[str, object]], None]
SORTS = ("mostrecent", "mosthelpful")


def load_reviews(
    app: str,
    *,
    countries: tuple[str, ...] | None = None,
    sort: str = "mostrecent",
    workers: int = 8,
    on_status: StatusCallback | None = None,
) -> dict[str, object]:
    if sort not in SORTS:
        raise ItunesError("sort must be mostrecent or mosthelpful")
    if workers < 1:
        raise ItunesError("workers must be at least 1")

    app_id = parse_app_id(app)
    selected = countries if countries is not None else STOREFRONTS
    _emit(on_status, {"kind": "scan", "count": len(selected), "app_id": app_id})

    storefronts, failures = scan_storefronts(app_id, selected, workers)
    for message in failures:
        _emit(on_status, {"kind": "failure", "message": message})

    with_ratings = [item for item in storefronts if item.rating_count > 0]
    if not storefronts:
        raise AppNotFound("App was not found in any of the scanned storefronts.")
    if not with_ratings:
        name = next((item.name for item in storefronts if item.name), app_id)
        _emit(on_status, {"kind": "empty", "name": name, "app_id": app_id})
        return _payload(app_id, name, [], [], failures, app=None)

    name = with_ratings[0].name or app_id
    try:
        app_meta = lookup_metadata(app_id, with_ratings[0].country)
    except ItunesError:
        app_meta = None
    _emit(
        on_status,
        {
            "kind": "ratings",
            "name": name,
            "app_id": app_id,
            "storefronts": [
                {"country": item.country, "rating_count": item.rating_count}
                for item in with_ratings
            ],
        },
    )

    country_reviews, fetch_failures = fetch_storefront_reviews(
        app_id,
        tuple(item.country for item in with_ratings),
        sort,
        workers,
    )
    failures = [*failures, *fetch_failures]
    for message in fetch_failures:
        _emit(on_status, {"kind": "failure", "message": message})

    reviews = [review for batch in country_reviews for review in batch.reviews]
    reviews.sort(key=lambda review: review.updated or "", reverse=True)
    for batch in country_reviews:
        _emit(
            on_status,
            {
                "kind": "fetched",
                "country": batch.country,
                "review_count": len(batch.reviews),
                "truncated": batch.truncated,
            },
        )
    return _payload(
        app_id,
        name,
        with_ratings,
        reviews,
        failures,
        country_reviews,
        app_meta,
    )


def _emit(on_status: StatusCallback | None, event: dict[str, object]) -> None:
    if on_status is not None:
        on_status(event)


def _payload(
    app_id: str,
    name: str,
    storefronts: list[Storefront],
    reviews: list[Review],
    failures: list[str],
    country_reviews: list[CountryReviews] | None = None,
    app: dict[str, object] | None = None,
) -> dict[str, object]:
    counts = {batch.country: batch for batch in country_reviews or []}
    return {
        "app_id": app_id,
        "name": name,
        "failures": failures,
        "app": app,
        "storefronts": [
            {
                "country": item.country,
                "rating_count": item.rating_count,
                "current_version_rating_count": item.current_version_rating_count,
                "average_rating": item.average_rating,
                "review_count": len(counts[item.country].reviews)
                if item.country in counts
                else 0,
                "truncated": counts[item.country].truncated
                if item.country in counts
                else False,
                "partial": counts[item.country].partial
                if item.country in counts
                else False,
            }
            for item in storefronts
        ],
        "reviews": [review.as_dict() for review in reviews],
    }
