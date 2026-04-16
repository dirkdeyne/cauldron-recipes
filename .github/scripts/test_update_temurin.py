"""Unit tests for update_temurin.py — all HTTP calls are mocked."""

import json
import pytest
from update_temurin import _parse_tag, build_entry, run

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOWS_SHA = "06ac5f5444a1269dd11d11cbb7ab6e592f2304bca583a7ef3f03986a4afb8312"
FAKE_SHA256_FILE = f"{WINDOWS_SHA}  OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10.zip"

FAKE_EOL_RESPONSE = """
{
  "schema_version": "1.2.1",
  "generated_at": "2026-04-16T02:03:04+00:00",
  "last_modified": "2026-01-27T01:03:49+00:00",
  "result": {
    "name": "eclipse-temurin",
    "aliases": ["temurin"],
    "label": "Eclipse Temurin",
    "category": "lang",
    "tags": ["eclipse", "java-distribution", "lang"],
    "versionCommand": "java -version",
    "identifiers": [],
    "labels": {"eoas": null, "discontinued": null, "eol": "Security Support", "eoes": null},
    "links": {
      "icon": "https://cdn.jsdelivr.net/npm/simple-icons/icons/eclipseadoptium.svg",
      "html": "https://endoflife.date/eclipse-temurin",
      "releasePolicy": "https://adoptium.net/support/"
    },
    "releases": [
      {
        "name": "25",
        "latest": {
          "name": "25.0.2+10",
          "date": "2026-01-22",
          "link": "https://github.com/adoptium/temurin25-binaries/releases/tag/jdk-25.0.2+10"
        }
      },
      {
        "name": "22",
        "latest": {
          "name": "22.0.2+9",
          "date": "2024-07-17",
          "link": "https://github.com/adoptium/temurin22-binaries/releases/tag/jdk-22.0.2+9"
        }
      },
      {
        "name": "8",
        "latest": {
          "name": "8u482-b08",
          "date": "2026-01-26",
          "link": "https://github.com/adoptium/temurin8-binaries/releases/tag/jdk8u482-b08"
        }
      }
    ]
  }
}
"""


# ---------------------------------------------------------------------------
# _parse_tag
# ---------------------------------------------------------------------------

class TestParseTag:
    def test_modern_tag(self):
        major, stem = _parse_tag("jdk-25.0.2+10")
        assert major == "25"
        assert stem == "OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10"

    def test_modern_tag_different_version(self):
        major, stem = _parse_tag("jdk-22.0.2+9")
        assert major == "22"
        assert stem == "OpenJDK22U-jdk_x64_windows_hotspot_22.0.2_9"

    def test_java8_tag(self):
        major, stem = _parse_tag("jdk8u482-b08")
        assert major == "8"
        assert stem == "OpenJDK8U-jdk_x64_windows_hotspot_8u482b08"

    def test_invalid_tag_returns_none(self):
        assert _parse_tag("not-a-tag") is None
        assert _parse_tag("") is None
        assert _parse_tag("jdk-25") is None  # missing semver and build


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------

class TestBuildEntry:
    RELEASE_25 = {
        "latest": {"link": "https://github.com/adoptium/temurin25-binaries/releases/tag/jdk-25.0.2+10"}
    }
    RELEASE_8 = {
        "latest": {"link": "https://github.com/adoptium/temurin8-binaries/releases/tag/jdk8u482-b08"}
    }

    def test_modern_happy_path(self):
        entry = build_entry("25", self.RELEASE_25, fetcher=lambda url: FAKE_SHA256_FILE)
        assert entry["version"] == "25"
        assert "OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10.zip" in entry["url"]
        assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_java8_happy_path(self):
        entry = build_entry("8", self.RELEASE_8, fetcher=lambda url: FAKE_SHA256_FILE)
        assert entry["version"] == "8"
        assert "OpenJDK8U-jdk_x64_windows_hotspot_8u482b08.zip" in entry["url"]
        assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_url_uses_correct_major_repo(self):
        entry = build_entry("25", self.RELEASE_25, fetcher=lambda url: FAKE_SHA256_FILE)
        assert "temurin25-binaries" in entry["url"]

    def test_java8_url_uses_correct_repo(self):
        entry = build_entry("8", self.RELEASE_8, fetcher=lambda url: FAKE_SHA256_FILE)
        assert "temurin8-binaries" in entry["url"]

    def test_plus_encoded_in_url(self):
        entry = build_entry("25", self.RELEASE_25, fetcher=lambda url: FAKE_SHA256_FILE)
        assert "%2B" in entry["url"]
        assert "+" not in entry["url"]

    def test_sha256_hash_only_file(self):
        entry = build_entry("25", self.RELEASE_25, fetcher=lambda url: WINDOWS_SHA)
        assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_no_github_link(self):
        entry = build_entry("25", {}, fetcher=lambda url: FAKE_SHA256_FILE)
        assert entry["checksums"] == {}
        assert entry["version"] == "25"

    def test_fetcher_failure_returns_empty_checksums(self):
        def bad_fetcher(url):
            raise Exception("network error")
        entry = build_entry("25", self.RELEASE_25, fetcher=bad_fetcher)
        assert entry["checksums"] == {}

    def test_invalid_tag_format(self):
        release = {"latest": {"link": "https://github.com/adoptium/temurin25-binaries/releases/tag/not-a-tag"}}
        entry = build_entry("25", release, fetcher=lambda url: FAKE_SHA256_FILE)
        assert entry["checksums"] == {}


# ---------------------------------------------------------------------------
# run (integration-level, fully mocked)
# ---------------------------------------------------------------------------

class TestRun:
    def _fetcher(self, url):
        if "endoflife" in url:
            return FAKE_EOL_RESPONSE
        if ".sha256.txt" in url:
            return FAKE_SHA256_FILE
        raise Exception(f"Unexpected URL in test: {url}")

    def test_returns_one_entry_per_release(self):
        assert len(run(fetcher=self._fetcher)) == 3

    def test_versions_match(self):
        versions = [r["version"] for r in run(fetcher=self._fetcher)]
        assert "25" in versions
        assert "22" in versions
        assert "8" in versions

    def test_checksums_populated(self):
        for entry in run(fetcher=self._fetcher):
            assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_skips_entries_without_name(self):
        eol = json.dumps({"result": {"releases": [{"latest": {}}]}})  # no "name"

        def fetcher(url):
            return eol if "endoflife" in url else FAKE_SHA256_FILE

        assert run(fetcher=fetcher) == []

    def test_skips_entries_with_bad_checksums(self):
        def fetcher(url):
            if "endoflife" in url:
                return FAKE_EOL_RESPONSE
            raise Exception("network error")

        assert run(fetcher=fetcher) == []

    def test_eol_releases_included(self):
        # version 22 is EOL in the fixture but should still be processed
        versions = [r["version"] for r in run(fetcher=self._fetcher)]
        assert "22" in versions