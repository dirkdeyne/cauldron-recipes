"""Unit tests for update_corretto.py — all HTTP calls are mocked."""

import json
import pytest
from unittest.mock import patch
from update_corretto import ReleaseTableParser, _parse_checksums, build_entry, run

# ---------------------------------------------------------------------------
# Minimal HTML table that matches the real GitHub release page structure
# ---------------------------------------------------------------------------

WINDOWS_MD5 = "403888fc1d84a8d7a823ad7ff3ecc589"
WINDOWS_SHA = "ea03f291937e6b32700fa325ec2bf77dcf570f1ace8ef0f01e752d66c035877e"

FAKE_RELEASE_HTML = f"""
<table>
  <tr>
    <td>Linux x64</td>
    <td>JDK</td>
    <td><a href="https://corretto.aws/downloads/resources/21.0.10.7.1/amazon-corretto-21.0.10.7.1-linux-x64.tar.gz">linux.tar.gz</a></td>
    <td><code>aabbccdd11223344556677889900aabb</code> / <code>{"a" * 64}</code></td>
    <td></td>
  </tr>
  <tr>
    <td>Windows x64</td>
    <td>JDK</td>
    <td><a href="https://corretto.aws/downloads/resources/21.0.10.7.1/amazon-corretto-21.0.10.7.1-windows-x64-jdk.zip">windows-x64-jdk.zip</a></td>
    <td><code>{WINDOWS_MD5}</code> / <code>{WINDOWS_SHA}</code></td>
    <td></td>
  </tr>
</table>
"""

FAKE_EOL_RESPONSE = """
{
  "schema_version": "1.2.1",
  "generated_at": "2026-04-12T01:50:24+00:00",
  "last_modified": "2026-04-01T01:29:53+00:00",
  "result": {
    "name": "amazon-corretto",
    "aliases": [
      "corretto"
    ],
    "label": "Amazon Corretto",
    "category": "lang",
    "tags": [
      "amazon",
      "java-distribution",
      "lang"
    ],
    "versionCommand": "java -version",
    "identifiers": [
      {
        "type": "cpe",
        "id": "cpe:/a:amazon:corretto"
      },
      {
        "type": "cpe",
        "id": "cpe:2.3:a:amazon:corretto"
      },
      {
        "type": "purl",
        "id": "pkg:docker/library/amazoncorretto"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-26"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-25"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-24"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-23"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-22"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-21"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-20"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-19"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-18"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-17"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-11"
      },
      {
        "type": "purl",
        "id": "pkg:github/corretto/corretto-8"
      }
    ],
    "labels": {
      "eoas": null,
      "discontinued": null,
      "eol": "Security Support",
      "eoes": null
    },
    "links": {
      "icon": "https://cdn.jsdelivr.net/npm/simple-icons/icons/openjdk.svg",
      "html": "https://endoflife.date/amazon-corretto",
      "releasePolicy": "https://aws.amazon.com/corretto/faqs/"
    },
    "releases": [
      {
        "name": "21",
        "codename": null,
        "label": "21 (LTS)",
        "releaseDate": "2023-08-25",
        "isLts": true,
        "ltsFrom": null,
        "isEol": false,
        "eolFrom": "2030-10-31",
        "isMaintained": true,
        "latest": {
          "name": "21.0.10.7.1",
          "date": "2026-01-20",
          "link": "https://github.com/corretto/corretto-21/releases/tag/21.0.10.7.1"
        },
        "custom": null
      },
      {
        "name": "17",
        "codename": null,
        "label": "17 (LTS)",
        "releaseDate": "2021-08-24",
        "isLts": true,
        "ltsFrom": null,
        "isEol": false,
        "eolFrom": "2029-10-31",
        "isMaintained": true,
        "latest": {
          "name": "17.0.18.9.1",
          "date": "2026-01-29",
          "link": "https://github.com/corretto/corretto-17/releases/tag/17.0.18.9.1"
        },
        "custom": null
      }
    ]
  }
}
"""


# ---------------------------------------------------------------------------
# _parse_checksums
# ---------------------------------------------------------------------------

class TestParseChecksums:
    def test_extracts_md5_and_sha256(self):
        text = f"`{WINDOWS_MD5}` /  `{WINDOWS_SHA}`"
        result = _parse_checksums(text)
        assert result["MD5"] == WINDOWS_MD5
        assert result["SHA-256"] == WINDOWS_SHA

    def test_empty_string(self):
        assert _parse_checksums("") == {}

    def test_only_md5(self):
        result = _parse_checksums(f"`{WINDOWS_MD5}`")
        assert result == {"MD5": WINDOWS_MD5}

    def test_only_sha256(self):
        result = _parse_checksums(f"`{WINDOWS_SHA}`")
        assert result == {"SHA-256": WINDOWS_SHA}

    def test_lowercases_hashes(self):
        result = _parse_checksums(WINDOWS_MD5.upper())
        assert result["MD5"] == WINDOWS_MD5.lower()


# ---------------------------------------------------------------------------
# ReleaseTableParser
# ---------------------------------------------------------------------------

class TestReleaseTableParser:
    def test_extracts_windows_row(self):
        result = ReleaseTableParser.parse(FAKE_RELEASE_HTML)
        assert result["MD5"] == WINDOWS_MD5
        assert result["SHA-256"] == WINDOWS_SHA

    def test_ignores_non_windows_rows(self):
        html = """
        <table><tr>
          <td>Linux x64</td><td>JDK</td>
          <td><a href="https://example.com/linux-x64.tar.gz">linux</a></td>
          <td><code>aabbccdd11223344556677889900aabb</code> / <code>{"b" * 64}</code></td>
          <td></td>
        </tr></table>
        """
        assert ReleaseTableParser.parse(html) == {}

    def test_empty_html(self):
        assert ReleaseTableParser.parse("") == {}

    def test_no_table(self):
        assert ReleaseTableParser.parse("<p>No table here</p>") == {}


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------

class TestBuildEntry:
    RELEASE = {
        "latest":
            {"link": "https://github.com/corretto/corretto-21/releases/tag/21.0.10.7.1"}
    }

    def test_happy_path(self):
        with patch("update_corretto.fetch", return_value=FAKE_RELEASE_HTML):
            entry = build_entry("21", self.RELEASE)
        print(entry)
        assert entry["version"] == "21"
        assert entry["url"].endswith("amazon-corretto-21-x64-windows-jdk.zip")
        assert entry["checksums"]["MD5"] == WINDOWS_MD5
        assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_no_github_link(self):
        entry = build_entry("21", {"links": []})
        assert entry["checksums"] == {}

# ---------------------------------------------------------------------------
# run (integration-level, fully mocked)
# ---------------------------------------------------------------------------

class TestRun:
    def _fetcher(self, url):
        if "endoflife" in url:
            return FAKE_EOL_RESPONSE
        if "github.com/corretto" in url:
            return FAKE_RELEASE_HTML
        raise Exception(f"Unexpected URL in test: {url}")

    def test_returns_one_entry_per_release(self):
        results = run(fetcher=self._fetcher)
        assert len(results) == 2

    def test_versions_match(self):
        results = run(fetcher=self._fetcher)
        versions = [r["version"] for r in results]
        assert "21" in versions
        assert "17" in versions

    def test_checksums_populated(self):
        results = run(fetcher=self._fetcher)
        for entry in results:
            assert entry["checksums"]["SHA-256"] == WINDOWS_SHA

    def test_skips_entries_without_name(self):
        eol = json.dumps({"releases": [{"links": []}]})  # no "name"

        def fetcher(url):
            return eol if "endoflife" in url else FAKE_RELEASE_HTML

        assert run(fetcher=fetcher) == []
