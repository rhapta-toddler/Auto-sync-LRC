"""Checks that the landing page in site/ keeps its SEO metadata valid and consistent."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parent.parent / "site"
SITE_URL = "https://rhapta-toddler.github.io/Auto-sync-LRC/"
DOWNLOAD_URL = (
    "https://github.com/rhapta-toddler/Auto-sync-LRC/releases/latest/download/"
    "Auto-sync-LRC-Setup.exe"
)


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = {}
        self.links = {}
        self.json_ld = []
        self.hrefs = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key:
                self.meta[key] = attrs.get("content", "")
        elif tag == "link" and "rel" in attrs:
            self.links[attrs["rel"]] = attrs.get("href", "")
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self._in_json_ld = True
            self.json_ld.append("")
        elif tag == "a" and "href" in attrs:
            self.hrefs.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_json_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_json_ld:
            self.json_ld[-1] += data


@pytest.fixture(scope="module")
def page():
    parser = _PageParser()
    parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
    return parser


def test_title_and_description_fit_search_snippets(page):
    assert "Auto-sync-LRC" in page.title
    assert ".lrc" in page.title
    assert 50 <= len(page.meta["description"]) <= 200


def test_canonical_and_og_url_point_at_the_site(page):
    assert page.links["canonical"] == SITE_URL
    assert page.meta["og:url"] == SITE_URL


def test_json_ld_blocks_parse_and_describe_the_app(page):
    blocks = [json.loads(raw) for raw in page.json_ld]
    by_type = {block["@type"]: block for block in blocks}

    app = by_type["SoftwareApplication"]
    assert app["downloadUrl"] == DOWNLOAD_URL
    assert app["url"] == SITE_URL
    assert app["offers"]["price"] == "0"

    faq = by_type["FAQPage"]
    assert len(faq["mainEntity"]) >= 3
    for question in faq["mainEntity"]:
        assert question["name"].endswith("?")
        assert question["acceptedAnswer"]["text"]


def test_download_buttons_use_the_stable_latest_release_link(page):
    assert page.hrefs.count(DOWNLOAD_URL) >= 2


def test_json_ld_version_matches_the_package():
    pyproject = (SITE.parent / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert f'"softwareVersion": "{version}"' in html


@pytest.mark.parametrize("name", ["robots.txt", "sitemap.xml", "llms.txt"])
def test_crawler_files_reference_the_site_url(name):
    assert SITE_URL in (SITE / name).read_text(encoding="utf-8")
