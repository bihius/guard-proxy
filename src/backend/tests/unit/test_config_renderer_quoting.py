import pytest

from app.services.config_renderer import _quote_modsec


def test_quote_modsec_escapes_quotes_but_preserves_backslashes() -> None:
    # A regex with escapes must not be doubled, or Coraza will see literal backslashes.
    assert _quote_modsec(r"^/api\.txt$") == r"^/api\.txt$"
    assert _quote_modsec(r"\d+\s+") == r"\d+\s+"

    # Quotes are escaped so they do not break the SecRule format.
    assert _quote_modsec('exact "match"') == r'exact \"match\"'

    # Both combined.
    assert _quote_modsec(r'path\.txt "quoted"') == r'path\.txt \"quoted\"'


def test_quote_modsec_rejects_unparseable_edge_cases() -> None:
    # A trailing backslash would escape the closing quote of the directive.
    with pytest.raises(ValueError, match="end with a backslash"):
        _quote_modsec(r"C:\temp\\")

    # A backslash before a quote becomes \\" when the quote is escaped, which
    # Coraza misparses as an unescaped quote (since the backslashes cancel out),
    # breaking the directive syntax. Coraza's UnescapeQuotedString also cannot
    # produce this sequence.
    with pytest.raises(ValueError, match="backslash followed by a quote"):
        _quote_modsec(r'literal \" quote')
