"""Demo page content as raw StreamField JSON, which every supported Wagtail accepts."""

import json
import uuid


def _id():
    return str(uuid.uuid4())


def demo_stream():
    """``body``: a heading, a section holding text and a card grid, and a list of tags.

    ``sidebar``: a note.
    """
    cards = [
        {"type": "item", "id": _id(), "value": {"headline": "First card", "link_text": "Read more"}},
        {"type": "item", "id": _id(), "value": {"headline": "Second card", "link_text": ""}},
    ]
    tags = [
        {"type": "item", "id": _id(), "value": "News"},
        {"type": "item", "id": _id(), "value": "Events"},
    ]
    content = [
        {"type": "text", "id": _id(), "value": "<p>Section copy</p>"},
        {"type": "card_grid", "id": _id(), "value": {"cards": cards}},
    ]
    return {
        "body": json.dumps(
            [
                {"type": "heading", "id": _id(), "value": "Welcome"},
                {"type": "section", "id": _id(), "value": {"style": "plain", "content": content}},
                {"type": "tags", "id": _id(), "value": tags},
            ]
        ),
        "sidebar": json.dumps([{"type": "note", "id": _id(), "value": "Sidebar note"}]),
    }
