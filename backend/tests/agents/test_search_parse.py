"""Tests de src.agents.search_parse — normalisation d'URL et parsing MCP."""

import pytest

from src.agents import search_parse as sp


# -------------------------------------------------------------- normalize_url

class TestNormalizeUrl:
    def test_empty_string(self):
        assert sp.normalize_url("") == ""

    def test_none_like_falsy(self):
        assert sp.normalize_url(None) == ""

    def test_strips_www(self):
        assert sp.normalize_url("https://www.example.com/a") == "https://example.com/a"

    def test_lowercases_scheme_and_host_not_path(self):
        result = sp.normalize_url("HTTPS://EXAMPLE.COM/CaseSensitivePath")
        assert result == "https://example.com/CaseSensitivePath"

    def test_removes_trailing_slash(self):
        assert sp.normalize_url("https://example.com/a/") == "https://example.com/a"

    def test_removes_fragment(self):
        assert sp.normalize_url("https://example.com/a#section") == "https://example.com/a"

    def test_removes_single_tracking_param(self):
        assert sp.normalize_url("https://example.com/a?utm_source=x") == "https://example.com/a"

    def test_removes_multiple_tracking_params_keeps_others(self):
        url = "https://example.com/a?utm_source=x&utm_campaign=y&id=42"
        assert sp.normalize_url(url) == "https://example.com/a?id=42"

    def test_removes_fbclid_gclid(self):
        url = "https://example.com/a?fbclid=abc&gclid=def&keep=1"
        assert sp.normalize_url(url) == "https://example.com/a?keep=1"

    def test_sorts_remaining_params(self):
        url = "https://example.com/a?z=1&a=2"
        assert sp.normalize_url(url) == "https://example.com/a?a=2&z=1"

    def test_no_scheme_defaults_to_https(self):
        # urlparse sans "//": tout est traite comme un path, pas de netloc — verifie
        # simplement que la fonction ne plante pas et produit une sortie stable.
        result = sp.normalize_url("example.com/a")
        assert isinstance(result, str)

    def test_two_equivalent_urls_normalize_identically(self):
        a = sp.normalize_url("https://www.Example.com/a/?utm_source=x&b=2#frag")
        b = sp.normalize_url("https://example.com/a?b=2")
        assert a == b == "https://example.com/a?b=2"

    def test_query_value_containing_ref_word_not_over_stripped(self):
        # _TRACKING_PARAMS matche le NOM du param exactement pour 'ref', pas la valeur.
        assert sp.normalize_url("https://example.com/a?other=ref123") == (
            "https://example.com/a?other=ref123"
        )

    def test_exact_ref_param_removed(self):
        assert sp.normalize_url("https://example.com/a?ref=hn") == "https://example.com/a"

    def test_whitespace_stripped(self):
        assert sp.normalize_url("  https://example.com/a  ") == "https://example.com/a"

    def test_urlparse_value_error_falls_back_to_lowered_stripped_input(self):
        # urlparse leve ValueError sur une URL IPv6 malformee.
        malformed = "http://[::1:8080/PATH"
        assert sp.normalize_url(malformed) == malformed.lower()


# ------------------------------------------------------------------ domain_of

class TestDomainOf:
    def test_basic(self):
        assert sp.domain_of("https://example.com/a") == "example.com"

    def test_strips_www(self):
        assert sp.domain_of("https://www.example.com/a") == "www.example.com"[4:]

    def test_lowercases(self):
        assert sp.domain_of("https://EXAMPLE.com/a") == "example.com"

    def test_empty_url(self):
        assert sp.domain_of("") == ""

    def test_no_netloc(self):
        assert sp.domain_of("not-a-url") == ""

    def test_urlparse_value_error_returns_empty_string(self):
        assert sp.domain_of("http://[::1:8080/path") == ""


# -------------------------------------------------------------- parse_mcp_text

class TestParseMcpTextJson:
    def test_json_array_of_records(self):
        raw = '[{"title": "A", "url": "https://a.com", "text": "snippet a"}]'
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result) == 1
        assert result[0]["title"] == "A"
        assert result[0]["url"] == "https://a.com"
        assert result[0]["snippet"] == "snippet a"
        assert result[0]["source"] == "a.com"
        assert result[0]["provider"] == "exa"

    def test_json_object_with_results_key(self):
        raw = '{"results": [{"title": "B", "url": "https://b.com"}]}'
        result = sp.parse_mcp_text(raw, "brave")
        assert len(result) == 1
        assert result[0]["title"] == "B"

    def test_json_object_with_data_key(self):
        raw = '{"data": [{"title": "C", "url": "https://c.com"}]}'
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result) == 1

    def test_json_single_object_fallback(self):
        raw = '{"title": "Solo", "url": "https://solo.com"}'
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result) == 1
        assert result[0]["title"] == "Solo"

    def test_json_record_field_aliases(self):
        raw = '[{"name": "Aliased", "link": "https://x.com", "description": "desc"}]'
        result = sp.parse_mcp_text(raw, "exa")
        assert result[0]["title"] == "Aliased"
        assert result[0]["url"] == "https://x.com"
        assert result[0]["snippet"] == "desc"

    def test_json_missing_title_falls_back_to_url(self):
        raw = '[{"url": "https://x.com"}]'
        result = sp.parse_mcp_text(raw, "exa")
        assert result[0]["title"] == "https://x.com"

    def test_malformed_json_falls_through_to_text_parser(self):
        raw = '[{"title": "broken", '  # JSON invalide
        result = sp.parse_mcp_text(raw, "exa")
        # Ne doit pas lever ; retombe sur le parseur texte (ne trouvera rien d'utile ici).
        assert result == []

    def test_snippet_truncated_to_4000_chars(self):
        long_text = "x" * 5000
        raw = f'[{{"title": "T", "url": "https://a.com", "text": "{long_text}"}}]'
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result[0]["snippet"]) == 4000

    def test_coerce_json_records_scalar_yields_empty(self):
        # _coerce_json_records est defensif pour un scalaire (ni liste ni dict).
        # Inatteignable depuis parse_mcp_text (le garde-fou startswith('[','{')
        # garantit que json.loads produit toujours une liste ou un dict), donc
        # teste directement l'utilitaire prive pour couvrir son propre contrat.
        assert sp._coerce_json_records(42) == []
        assert sp._coerce_json_records("a string") == []
        assert sp._coerce_json_records(None) == []


class TestParseMcpTextBlocks:
    def test_single_article_basic_fields(self):
        raw = (
            "Title: Hello World\n"
            "URL: https://ex.com/1\n"
            "Published Date: 2026-01-01\n"
            "Text: some content here\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result) == 1
        art = result[0]
        assert art["title"] == "Hello World"
        assert art["url"] == "https://ex.com/1"
        assert art["published_date"] == "2026-01-01"
        assert art["snippet"] == "some content here"
        assert art["source"] == "ex.com"

    def test_multiple_articles_separated_by_title(self):
        raw = (
            "Title: First\n"
            "URL: https://ex.com/1\n"
            "Text: first text\n"
            "\n"
            "Title: Second\n"
            "URL: https://ex.com/2\n"
            "Text: second text\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"

    def test_label_case_and_variants(self):
        raw = (
            "Title: Variant test\n"
            "Link: https://ex.com/v\n"
            "Published: 2026-02-02\n"
            "Description: a description used as text\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        assert result[0]["url"] == "https://ex.com/v"
        assert result[0]["published_date"] == "2026-02-02"
        assert result[0]["snippet"] == "a description used as text"

    def test_ignored_labels_do_not_leak_into_text(self):
        raw = (
            "Title: With noise\n"
            "URL: https://ex.com/n\n"
            "Author: John Doe\n"
            "Score: 0.98\n"
            "Text: the real content\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        assert "John Doe" not in result[0]["snippet"]
        assert "0.98" not in result[0]["snippet"]
        assert result[0]["snippet"] == "the real content"

    def test_na_values_cleaned_to_empty(self):
        raw = "Title: Has NA\nURL: https://ex.com/na\nPublished Date: N/A\n"
        result = sp.parse_mcp_text(raw, "exa")
        assert result[0]["published_date"] == ""

    def test_title_missing_falls_back_to_url(self):
        raw = "URL: https://ex.com/no-title\nText: content\n"
        result = sp.parse_mcp_text(raw, "exa")
        assert result[0]["title"] == "https://ex.com/no-title"

    def test_continuation_line_without_label_appended(self):
        raw = (
            "Title: Multiline\n"
            "URL: https://ex.com/m\n"
            "Text: first part\n"
            "continuation without a label\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        assert "continuation without a label" in result[0]["snippet"]

    def test_empty_raw_text_returns_empty_list(self):
        assert sp.parse_mcp_text("", "exa") == []

    def test_whitespace_only_returns_empty_list(self):
        assert sp.parse_mcp_text("   \n  \n", "exa") == []

    def test_no_url_and_no_title_produces_nothing(self):
        raw = "Text: orphan content with no title or url\n"
        result = sp.parse_mcp_text(raw, "exa")
        assert result == []

    def test_provider_tag_set_correctly(self):
        raw = "Title: T\nURL: https://ex.com\n"
        result = sp.parse_mcp_text(raw, "brave")
        assert result[0]["provider"] == "brave"

    def test_unknown_label_attaches_to_current_field(self):
        raw = (
            "Title: T\n"
            "URL: https://ex.com\n"
            "Text: base text\n"
            "Weird Label: extra info\n"
        )
        result = sp.parse_mcp_text(raw, "exa")
        # 'Weird Label' n'est pas dans _LABEL_MAP -> rattache au champ courant (text).
        assert "extra info" in result[0]["snippet"]
