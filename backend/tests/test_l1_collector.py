"""Tests for batch.l1_collector module."""

from __future__ import annotations

from datetime import datetime, timezone

from batch.l1_collector import (
    compute_date_range,
    deduplicate,
    extract_arxiv_id,
    parse_entries,
)
from utils.models import ArxivPaper

# ---------------------------------------------------------------------------
# テスト用 XML
# ---------------------------------------------------------------------------
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2402.12345v1</id>
    <title>  Test Paper Title
    with newlines  </title>
    <summary>This is a test abstract about LLMs and Transformers.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Chen</name></author>
    <published>2026-02-11T12:00:00Z</published>
    <updated>2026-02-11T12:00:00Z</updated>
    <link href="http://arxiv.org/pdf/2402.12345v1" title="pdf" type="application/pdf" rel="related"/>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.67890v2</id>
    <title>Another Paper</title>
    <summary>Abstract for another paper.</summary>
    <author><name>Carol Zhang</name></author>
    <published>2026-02-11T14:00:00Z</published>
    <link href="http://arxiv.org/pdf/2402.67890v2" title="pdf" type="application/pdf" rel="related"/>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
  </entry>
</feed>"""

EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""


# ---------------------------------------------------------------------------
# extract_arxiv_id
# ---------------------------------------------------------------------------
class TestExtractArxivId:
    """arXiv ID 抽出のテスト。"""

    def test_standard_id_with_version(self) -> None:
        assert extract_arxiv_id("http://arxiv.org/abs/2402.12345v1") == "2402.12345"

    def test_standard_id_without_version(self) -> None:
        assert extract_arxiv_id("http://arxiv.org/abs/2402.12345") == "2402.12345"

    def test_five_digit_id(self) -> None:
        assert extract_arxiv_id("http://arxiv.org/abs/2402.12345v2") == "2402.12345"

    def test_old_format_id(self) -> None:
        assert extract_arxiv_id("http://arxiv.org/abs/hep-ph/0601001v1") == "hep-ph/0601001"


# ---------------------------------------------------------------------------
# parse_entries
# ---------------------------------------------------------------------------
class TestParseEntries:
    """XML パースのテスト。"""

    def test_parses_two_entries(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert len(papers) == 2

    def test_extracts_arxiv_id(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert papers[0].arxiv_id == "2402.12345"
        assert papers[1].arxiv_id == "2402.67890"

    def test_normalizes_title(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        # 改行・余分な空白が正規化される
        assert "  " not in papers[0].title
        assert "\n" not in papers[0].title
        assert papers[0].title == "Test Paper Title with newlines"

    def test_extracts_authors(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert papers[0].authors == ["Alice Smith", "Bob Chen"]
        assert papers[1].authors == ["Carol Zhang"]

    def test_extracts_pdf_url(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert papers[0].pdf_url == "http://arxiv.org/pdf/2402.12345v1"

    def test_extracts_primary_category(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert papers[0].primary_category == "cs.CL"

    def test_extracts_all_categories(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert "cs.CL" in papers[0].all_categories
        assert "cs.LG" in papers[0].all_categories

    def test_sets_matched_queries(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=3)
        assert papers[0].matched_queries == [3]

    def test_empty_feed(self) -> None:
        papers = parse_entries(EMPTY_XML, category_id=1)
        assert papers == []

    def test_invalid_xml(self) -> None:
        papers = parse_entries("not xml at all", category_id=1)
        assert papers == []

    def test_published_at_parsed(self) -> None:
        papers = parse_entries(SAMPLE_XML, category_id=1)
        assert papers[0].published_at.year == 2026
        assert papers[0].published_at.month == 2


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------
class TestDeduplicate:
    """重複排除のテスト。"""

    def test_removes_duplicates(self) -> None:
        p1 = ArxivPaper(
            arxiv_id="2402.12345",
            title="Paper 1",
            abstract="Abstract 1",
            authors=["Author"],
            primary_category="cs.CL",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[1],
        )
        p2 = ArxivPaper(
            arxiv_id="2402.12345",
            title="Paper 1",
            abstract="Abstract 1",
            authors=["Author"],
            primary_category="cs.CL",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[3],
        )
        result = deduplicate([p1, p2])
        assert len(result) == 1

    def test_merges_matched_queries(self) -> None:
        p1 = ArxivPaper(
            arxiv_id="2402.12345",
            title="Paper 1",
            abstract="Abstract 1",
            authors=["Author"],
            primary_category="cs.CL",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[1],
        )
        p2 = ArxivPaper(
            arxiv_id="2402.12345",
            title="Paper 1",
            abstract="Abstract 1",
            authors=["Author"],
            primary_category="cs.CL",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[3],
        )
        result = deduplicate([p1, p2])
        assert set(result[0].matched_queries) == {1, 3}

    def test_keeps_unique_papers(self) -> None:
        p1 = ArxivPaper(
            arxiv_id="2402.11111",
            title="Paper 1",
            abstract="Abstract 1",
            authors=["Author"],
            primary_category="cs.CL",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[1],
        )
        p2 = ArxivPaper(
            arxiv_id="2402.22222",
            title="Paper 2",
            abstract="Abstract 2",
            authors=["Author"],
            primary_category="cs.LG",
            published_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
            matched_queries=[2],
        )
        result = deduplicate([p1, p2])
        assert len(result) == 2

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []


# ---------------------------------------------------------------------------
# compute_date_range
# ---------------------------------------------------------------------------
class TestComputeDateRange:
    """日付範囲計算のテスト。"""

    def test_returns_tuple(self) -> None:
        start, end = compute_date_range()
        assert isinstance(start, str)
        assert isinstance(end, str)

    def test_format(self) -> None:
        start, end = compute_date_range()
        # YYYYMMDD0000 形式
        assert len(start) == 12
        assert len(end) == 12
        assert start.endswith("0000")
        assert end.endswith("0000")

    def test_start_before_end(self) -> None:
        start, end = compute_date_range()
        assert start < end
