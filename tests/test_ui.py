"""Checks that the web interface is served correctly."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
PAGES = ["login.html", "triage.html", "consultations.html", "consultation.html", "protocols.html", "users.html", "audit.html"]


def test_root_redirects_to_login():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/login.html"


def test_every_page_is_served():
    for page in PAGES:
        r = client.get(f"/ui/{page}")
        assert r.status_code == 200, page
        assert "<title>" in r.text and "js/core.js" in r.text, page


def test_assets_are_served():
    assert client.get("/ui/css/app.css").status_code == 200
    assert client.get("/ui/js/core.js").status_code == 200
    assert client.get("/ui/fonts/Inter-Regular.woff2").status_code == 200


def test_pages_do_not_load_anything_from_the_internet():
    """The interface must work offline, so no page may load scripts, styles, or fonts from outside."""
    for page in PAGES + ["css/app.css", "js/core.js"]:
        # The SVG namespace (www.w3.org/2000/svg) is a label inside inline icons, not a download.
        text = (STATIC / page).read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
        for bad in ("http://", "https://", "//cdn", "googleapis"):
            assert bad not in text.replace("http://127.0.0.1", ""), f"{page} references {bad}"
