"""server/config/server.properties.example delivers the client pack ADR-006 describes, and its sha1 is the build's.

The pack itself (build/client/cobblers-client-AllTheMons-subset.zip) holds third-party assets and is never committed,
so the comparison with a built pack runs only where one has been built; everywhere else the example is checked
against the documents that quote the same sha1, and against its own declared derivations (the UUID's name, the
prompt's JSON form).

Not covered: that a client downloads and applies the pack, that the URL works, or that the licence permission exists.
Those are an in-game check and an owner act.
"""
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import client_model_fix as CMF  # noqa: E402

EXAMPLE = ROOT / "server" / "config" / "server.properties.example"
ADR = ROOT / "docs" / "decisions" / "ADR-006-server-delivered-client-pack.md"
FIXES_DOC = ROOT / "docs" / "research" / "CLIENT_MODEL_FIXES.md"
BUILT = ROOT / "build" / "client" / CMF.SERVER_PACK_NAME
ID_NAME = "cobblers:client-pack/" + CMF.SERVER_PACK_NAME[: -len(".zip")]


def props():
    out = {}
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        assert k not in out, "duplicate key %s" % k
        out[k] = v
    return out


def test_the_pack_keys_are_all_present_once():
    p = props()
    for k in ("require-resource-pack", "resource-pack", "resource-pack-sha1", "resource-pack-id",
              "resource-pack-prompt"):
        assert k in p, k
    assert p["require-resource-pack"] == "true"


def test_url_is_empty_or_https():
    # empty means no pack is sent; anything else must be a direct HTTPS link every client can reach
    url = props()["resource-pack"]
    assert url == "" or url.startswith("https://"), url


def test_sha1_is_a_sha1():
    assert re.fullmatch(r"[0-9a-f]{40}", props()["resource-pack-sha1"])


def test_sha1_is_the_one_the_documents_quote():
    s = props()["resource-pack-sha1"]
    assert s in ADR.read_text(encoding="utf-8"), "ADR-006 quotes a different pack"
    assert s in FIXES_DOC.read_text(encoding="utf-8"), "CLIENT_MODEL_FIXES.md quotes a different pack"


def test_pack_id_is_the_declared_fixed_uuid():
    pid = props()["resource-pack-id"]
    assert str(uuid.UUID(pid)) == pid
    assert pid == str(uuid.uuid5(uuid.NAMESPACE_URL, ID_NAME))
    assert ID_NAME in EXAMPLE.read_text(encoding="utf-8"), "the comment must name what the UUID is derived from"


def test_prompt_is_a_short_ascii_text_component_with_the_credit():
    raw = props()["resource-pack-prompt"]
    assert raw.isascii()
    doc = json.loads(raw)
    assert isinstance(doc, dict) and isinstance(doc.get("text"), str)
    assert "AllTheMons" in doc["text"] and "Lvnatic" in doc["text"]
    assert len(doc["text"]) <= 200


@pytest.mark.skipif(not BUILT.is_file(), reason="no built pack in build/client (it is never committed)")
def test_sha1_matches_the_built_pack():
    s = props()["resource-pack-sha1"]
    side = BUILT.with_name(BUILT.name + ".sha1")
    assert side.read_text(encoding="ascii").strip() == s, "rebuilt pack: update resource-pack-sha1 and the documents"
    assert hashlib.sha1(BUILT.read_bytes()).hexdigest() == s
