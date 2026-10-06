"""Public iTunes endpoints for ratings and written reviews.

Anyone can call these. They do not require an App Store Connect account.
Each storefront returns at most 10 pages of 50 written reviews.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

USER_AGENT = "Mozilla/5.0"
MAX_PAGES = 10
PAGE_SIZE = 50
_ATOM = "{http://www.w3.org/2005/Atom}"
_IM = "{http://itunes.apple.com/rss}"

_APP_ID_IN_URL = re.compile(r"/id(\d+)")
_BARE_APP_ID = re.compile(r"\d{5,}")


@dataclass(frozen=True)
class Review:
    country: str
    id: str
    rating: int
    title: str
    author: str
    content: str
    version: str | None
    updated: str | None
    vote_count: int
    vote_sum: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Storefront:
    country: str
    name: str | None
    rating_count: int
    current_version_rating_count: int
    average_rating: float | None


@dataclass(frozen=True)
class CountryReviews:
    country: str
    reviews: tuple[Review, ...]
    truncated: bool
    partial: bool = False


class ItunesError(Exception):
    pass


class InvalidAppId(ItunesError):
    pass


class AppNotFound(ItunesError):
    pass


def parse_app_id(value: str) -> str:
    text = value.strip()
    from_url = _APP_ID_IN_URL.search(text)
    if from_url:
        return from_url.group(1)
    if _BARE_APP_ID.fullmatch(text):
        return text
    raise InvalidAppId(
        "Pass an App Store URL or a numeric app id, "
        "for example https://apps.apple.com/jp/app/id443332137"
    )


def reviews_from_feed(payload: object, country: str) -> list[Review]:
    if not isinstance(payload, dict):
        return []
    feed = payload.get("feed")
    if not isinstance(feed, dict):
        return []
    entries = feed.get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    reviews: list[Review] = []
    for entry in entries:
        review = _review_from_entry(entry, country)
        if review is not None:
            reviews.append(review)
    return reviews


def lookup_storefront(app_id: str, country: str) -> Storefront | None:
    payload = _get_json(
        f"https://itunes.apple.com/lookup?id={app_id}&country={country}"
    )
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None
    app = results[0]
    if not isinstance(app, dict):
        return None
    average = app.get("averageUserRating")
    return Storefront(
        country=country,
        name=_optional_str(app.get("trackName")),
        rating_count=_optional_int(app.get("userRatingCount")) or 0,
        current_version_rating_count=_optional_int(
            app.get("userRatingCountForCurrentVersion")
        )
        or 0,
        average_rating=float(average) if isinstance(average, (int, float)) else None,
    )


def fetch_country_reviews(app_id: str, country: str, sort: str) -> CountryReviews:
    seen: set[str] = set()
    collected: list[Review] = []
    truncated = False
    partial = False
    for page in range(1, MAX_PAGES + 1):
        try:
            page_reviews = reviews_from_xml(
                _get_text(_reviews_url(app_id, country, page, sort)),
                country,
            )
        except ItunesError:
            if not collected:
                raise
            partial = True
            break
        new = [review for review in page_reviews if review.id not in seen]
        if not new:
            break
        seen.update(review.id for review in new)
        collected.extend(new)
        if page == MAX_PAGES and len(page_reviews) >= PAGE_SIZE:
            truncated = True
    return CountryReviews(
        country=country,
        reviews=tuple(collected),
        truncated=truncated,
        partial=partial,
    )


def lookup_metadata(app_id: str, country: str) -> dict[str, object] | None:
    payload = _get_json(
        f"https://itunes.apple.com/lookup?id={app_id}&country={country}"
    )
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None
    app = results[0]
    if not isinstance(app, dict):
        return None
    return metadata_from_result(app, country)


def metadata_from_result(app: dict[str, object], country: str) -> dict[str, object]:
    screenshots = app.get("screenshotUrls")
    genres = app.get("genres")
    average = app.get("averageUserRating")
    return {
        "country": country,
        "artwork": _optional_str(app.get("artworkUrl512"))
        or _optional_str(app.get("artworkUrl100")),
        "seller": _optional_str(app.get("artistName")),
        "price": _optional_str(app.get("formattedPrice")),
        "price_amount": app.get("price") if isinstance(app.get("price"), (int, float)) else None,
        "genres": [item for item in genres if isinstance(item, str)][:4]
        if isinstance(genres, list)
        else [],
        "released": _optional_str(app.get("releaseDate")),
        "updated": _optional_str(app.get("currentVersionReleaseDate")),
        "version": _optional_str(app.get("version")),
        "description": _optional_str(app.get("description")),
        "screenshots": [item for item in screenshots if isinstance(item, str)][:8]
        if isinstance(screenshots, list)
        else [],
        "url": _optional_str(app.get("trackViewUrl")),
        "average_rating": float(average) if isinstance(average, (int, float)) else None,
        "rating_count": _optional_int(app.get("userRatingCount")) or 0,
    }


def scan_storefronts(
    app_id: str, countries: tuple[str, ...], workers: int
) -> tuple[list[Storefront], list[str]]:
    found: list[Storefront] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for storefront, error in pool.map(
            lambda country: _guard(country, lambda: lookup_storefront(app_id, country)),
            countries,
        ):
            if error is not None:
                failures.append(error)
            elif storefront is not None:
                found.append(storefront)
    found.sort(key=lambda item: item.rating_count, reverse=True)
    return found, failures


def fetch_storefront_reviews(
    app_id: str, countries: tuple[str, ...], sort: str, workers: int
) -> tuple[list[CountryReviews], list[str]]:
    found: list[CountryReviews] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for batch, error in pool.map(
            lambda country: _guard(
                country, lambda: fetch_country_reviews(app_id, country, sort)
            ),
            countries,
        ):
            if error is not None:
                failures.append(error)
            elif batch is not None:
                found.append(batch)
    return found, failures


def _guard(country: str, call):
    try:
        return call(), None
    except ItunesError as error:
        return None, f"{country}: {error}"


def _reviews_url(app_id: str, country: str, page: int, sort: str) -> str:
    return (
        f"https://itunes.apple.com/{country}/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby={sort}/xml"
    )


def _review_from_entry(entry: object, country: str) -> Review | None:
    if not isinstance(entry, dict) or "im:rating" not in entry:
        return None
    review_id = _label(entry.get("id"))
    rating = _optional_int(_label(entry.get("im:rating")))
    title = _label(entry.get("title"))
    content = _label(entry.get("content"))
    if review_id is None or rating is None or title is None or content is None:
        return None
    author = entry.get("author")
    author_name = ""
    if isinstance(author, dict):
        author_name = _label(author.get("name")) or ""
    return Review(
        country=country,
        id=review_id,
        rating=rating,
        title=title,
        author=author_name,
        content=content,
        version=_label(entry.get("im:version")),
        updated=_label(entry.get("updated")),
        vote_count=_optional_int(_label(entry.get("im:voteCount"))) or 0,
        vote_sum=_optional_int(_label(entry.get("im:voteSum"))) or 0,
    )


def _label(node: object) -> str | None:
    if isinstance(node, dict):
        return _optional_str(node.get("label"))
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def reviews_from_xml(text: str, country: str) -> list[Review]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ItunesError("Apple returned a review feed that could not be read") from error
    reviews: list[Review] = []
    for entry in root.findall(f"{_ATOM}entry"):
        rating = _optional_int(_xml_text(entry.find(f"{_IM}rating")))
        review_id = _xml_text(entry.find(f"{_ATOM}id"))
        title = _xml_text(entry.find(f"{_ATOM}title"))
        content = _xml_content(entry)
        if review_id is None or rating is None or title is None or content is None:
            continue
        reviews.append(
            Review(
                country=country,
                id=review_id,
                rating=rating,
                title=title,
                author=_xml_text(entry.find(f"{_ATOM}author/{_ATOM}name")) or "",
                content=content,
                version=_xml_text(entry.find(f"{_IM}version")),
                updated=_xml_text(entry.find(f"{_ATOM}updated")),
                vote_count=_optional_int(_xml_text(entry.find(f"{_IM}voteCount"))) or 0,
                vote_sum=_optional_int(_xml_text(entry.find(f"{_IM}voteSum"))) or 0,
            )
        )
    return reviews


def _xml_text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _xml_content(entry: ET.Element) -> str | None:
    for node in entry.findall(f"{_ATOM}content"):
        if node.attrib.get("type") == "text" and node.text:
            return node.text
    return None


def _get_json(url: str) -> object:
    try:
        return json.loads(_get_text(url))
    except json.JSONDecodeError as error:
        raise ItunesError(f"Apple returned non-JSON for {url}") from error


def _get_text(url: str) -> str:
    delay = 0.7
    for attempt in range(3):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode()
        except urllib.error.HTTPError as error:
            blocked = error.code in (403, 429)
            error.close()
            if not blocked or attempt == 2:
                raise ItunesError(f"HTTP {error.code} for {url}") from error
        except urllib.error.URLError as error:
            raise ItunesError(f"Could not reach {url}: {error.reason}") from error
        time.sleep(delay)
        delay *= 2
    raise ItunesError(f"HTTP 403 for {url}")
