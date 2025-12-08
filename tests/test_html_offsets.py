from bs4 import BeautifulSoup

from html_offsets import find_html_fragment, map_text_offsets_to_html_range


def test_map_text_offsets_basic():
    html = "<p>Hello <strong>world</strong>!</p>"
    start, end = map_text_offsets_to_html_range(html, 0, 5)
    segment = html[start:end]
    assert BeautifulSoup(segment, "html.parser").get_text() == "Hello"


def test_map_text_offsets_through_tags():
    html = "<p>Hello <strong>world</strong>!</p>"
    start, end = map_text_offsets_to_html_range(html, 6, 11)
    segment = html[start:end]
    assert BeautifulSoup(segment, "html.parser").get_text() == "world"


def test_map_text_offsets_with_entities():
    html = "<p>&amp; &lt;test&gt;</p>"
    # Select "& "
    start, end = map_text_offsets_to_html_range(html, 0, 2)
    segment = html[start:end]
    assert BeautifulSoup(segment, "html.parser").get_text() == "& "
    # Select "<test>"
    start, end = map_text_offsets_to_html_range(html, 2, 8)
    segment = html[start:end]
    assert BeautifulSoup(segment, "html.parser").get_text() == "<test>"


def test_find_html_fragment_exact_html():
    document_html = "<p>Hello <strong>world</strong>!</p>"
    selection_html = "<strong>world</strong>"
    selection_text = "world"
    span = find_html_fragment(document_html, selection_text, selection_html, 6, 11)
    assert span is not None
    extracted = document_html[span.html_start : span.html_end]
    assert BeautifulSoup(extracted, "html.parser").get_text() == "world"


def test_find_html_fragment_wrapped_html():
    document_html = "<p>Hello <strong>world</strong>!</p>"
    selection_html = '<div data-test="x"><strong>world</strong></div>'
    selection_text = "world"
    span = find_html_fragment(document_html, selection_text, selection_html, 6, 11)
    assert span is not None
    extracted = document_html[span.html_start : span.html_end]
    assert BeautifulSoup(extracted, "html.parser").get_text() == "world"


def test_find_html_fragment_by_text_only():
    document_html = "<p>Alpha</p><p>Beta</p><p>Gamma</p>"
    selection_text = "Beta"
    span = find_html_fragment(document_html, selection_text, None, 6, 10)
    assert span is not None
    extracted = document_html[span.html_start : span.html_end]
    assert BeautifulSoup(extracted, "html.parser").get_text() == "Beta"

