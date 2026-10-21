import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Locale, Page, Site

import wagtail_block_ids.marks as marking_module
from wagtail_block_ids import install

# Apps call install() (via register_page_marker) from AppConfig.ready(); the test app has none.
install()


@pytest.fixture(autouse=True)
def _no_registered_markers(monkeypatch):
    """Each test registers only the markers it needs."""
    monkeypatch.setattr(marking_module, "_markers", [])


@pytest.fixture
def root_page(db):
    Locale.objects.get_or_create(language_code="en")
    root = Page.add_root(title="Root", slug="root")
    Site.objects.create(hostname="localhost", root_page=root, is_default_site=True)
    return root


@pytest.fixture
def demo_page(root_page):
    from testapp.factories import demo_stream
    from testapp.models import DemoPage

    page = root_page.add_child(instance=DemoPage(title="Demo", slug="demo", **demo_stream()))
    page.save_revision().publish()
    return page


@pytest.fixture
def editor(db):
    return get_user_model().objects.create_superuser("editor", "editor@example.com", "password")
