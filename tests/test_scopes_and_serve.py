"""Marking scopes, the page-marker registry, and marking real page serves."""

from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

import wagtail_block_ids.marks as marking_module
from wagtail_block_ids import block_ids, is_marking, marking, register_page_marker
from wagtail_block_ids.marks import _mark


class _Block:
    name = "text"
    label = "Text"


class _Bound:
    id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    block_type = "text"
    block = _Block()


# -- Scopes ---------------------------------------------------------------------------


def test_without_wrap_only_the_first_root_is_marked():
    with marking():
        multi = str(_mark(_Bound(), "<p>first</p><p>second</p>"))
        text = _mark(_Bound(), "plain text")

    assert multi.startswith('<p data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
    assert multi.count("data-block-id") == 1
    assert "display:contents" not in multi
    assert text == "plain text"


def test_nested_scopes_wrap_if_any_asks():
    with marking(), marking(wrap=True):
        assert "display:contents" in str(_mark(_Bound(), "<p>a</p><p>b</p>"))
    with marking(wrap=True), marking():
        assert "display:contents" in str(_mark(_Bound(), "<p>a</p><p>b</p>"))


def test_scope_closes_even_when_rendering_raises():
    with pytest.raises(RuntimeError), marking():
        raise RuntimeError

    assert not is_marking()


def test_already_marked_root_is_not_marked_twice():
    with marking():
        once = str(_mark(_Bound(), "<section>x</section>"))
        twice = str(_mark(_Bound(), once))

    assert twice == once
    assert twice.count("data-block-id") == 1


def test_a_childs_id_on_the_first_tag_does_not_stop_the_parent():
    with marking():
        out = str(_mark(_Bound(), '<h2 data-block-id="child">x</h2>'))

    assert out.startswith('<h2 data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')


# -- Page-marker registry ---------------------------------------------------------------


class _LazyResponse:
    def __init__(self):
        self.is_rendered = False
        self.rendered_while_marking = None

    def render(self):
        self.rendered_while_marking = is_marking()
        self.is_rendered = True


@pytest.fixture
def original_serve(monkeypatch):
    seen = []

    def fake_serve(page, request, *args, **kwargs):
        seen.append(marking_module._scope.get())
        return _LazyResponse()

    monkeypatch.setitem(marking_module._originals, "Page.serve", fake_serve)
    return seen


def _serve():
    return marking_module._patched_serve(SimpleNamespace(pk=1), SimpleNamespace(user=None))


def test_serve_is_untouched_without_a_willing_marker(original_serve):
    register_page_marker(lambda page, request: False, wrap=True)

    response = _serve()

    assert original_serve == [None]
    assert response.is_rendered is False


def test_serve_marks_and_renders_while_marking(original_serve):
    register_page_marker(lambda page, request: True)

    response = _serve()

    assert original_serve[0].wrap is False
    assert response.rendered_while_marking is True
    assert not is_marking()


def test_serve_wraps_if_any_willing_marker_asks(original_serve):
    register_page_marker(lambda page, request: True)
    register_page_marker(lambda page, request: True, wrap=True)
    register_page_marker(lambda page, request: False)

    _serve()

    assert original_serve[0].wrap is True


def test_serve_inside_an_open_scope_keeps_that_scope(original_serve):
    register_page_marker(lambda page, request: True)

    with marking(wrap=True):
        _serve()

    assert original_serve[0].wrap is True


# -- Real pages ----------------------------------------------------------------------------


def _editors_only(page, request):
    return getattr(request.user, "is_superuser", False)


def test_live_page_is_marked_for_whoever_a_marker_accepts(demo_page, editor):
    register_page_marker(_editors_only)
    client = Client()

    anonymous = client.get(demo_page.url).content.decode()
    client.force_login(editor)
    html = client.get(demo_page.url).content.decode()

    assert "data-block-id" not in anonymous
    for block_id in block_ids(demo_page):
        assert html.count(f'data-block-id="{block_id}"') == 1
    section = demo_page.body[1]
    assert f'<section data-block-id="{section.id}" data-block-type="section" data-block-label="Section"' in html


def test_preview_is_marked_through_serve_preview(demo_page, editor):
    register_page_marker(_editors_only)
    client = Client()
    client.force_login(editor)

    html = client.get(reverse("wagtailadmin_pages:view_draft", args=[demo_page.pk])).content.decode()

    for block_id in block_ids(demo_page):
        assert f'data-block-id="{block_id}"' in html


def test_block_ids_cover_every_stream_field_in_page_order(demo_page):
    section = demo_page.body[1]
    text, grid = section.value["content"]
    cards = grid.value["cards"].bound_blocks

    assert block_ids(demo_page) == [
        str(demo_page.body[0].id),
        str(section.id),
        str(text.id),
        str(grid.id),
        str(cards[0].id),
        str(cards[1].id),
        str(demo_page.sidebar[0].id),
    ]
