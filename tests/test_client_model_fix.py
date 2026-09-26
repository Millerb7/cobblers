"""tools/client_model_fix.py: the three scan rules classify models correctly, and the client pack build is exact.

Every model, texture, jar and resource pack here is synthetic, built in memory or under tmp_path: a fake Cobblemon jar
(a fabric.mod.json, a few bedrock files, an empty poser class name), a fake "Other.zip" pack that breaks three forms,
and a fake "ATMxMSD RP.zip" donor. No Cobblemon, Cobbleverse or AllTheMons asset is read or committed. The module's
SPAWNS, DONOR_PATHS and BASE_PACK_ORDER are pointed at tmp files, so the committed manifest is never rewritten.

Not covered: whether a flagged form actually crashes, shows the substitute doll or renders with a scrambled texture in
the client, and whether the built pack fixes it on screen. Those are runtime checks in a client (experiments/). The
rules are also only as good as their model of Cobblemon's resolution order, which these tests take from the tool.
"""
import hashlib
import io
import json
import os
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import client_model_fix as CMF  # noqa: E402

JAR_NAME = "Cobblemon-fabric-1.8.0+1.21.1.jar"
JAR = "mod:" + JAR_NAME
POSER_CLASS = CMF.POSER_CLASSES + "gen1/%sModel.class"
B = "assets/cobblemon/bedrock/pokemon/"


# ------------------------------------------------------------------ synthetic assets

def png(w, h) -> bytes:
    ihdr = struct.pack(">II", w, h) + b"\x08\x06\x00\x00\x00"
    chunk = struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk


def geo(bones, tw=64, th=64) -> bytes:
    """bones: {name: [(u, v), ...]}, one 2x2x2 box-UV cube per (u, v)."""
    return json.dumps({"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.x", "texture_width": tw, "texture_height": th},
        "bones": [{"name": n, "cubes": [{"origin": [0, 0, 0], "size": [2, 2, 2], "uv": list(uv)} for uv in uvs]}
                  for n, uvs in bones.items()]}]}).encode()


def model(d, name):
    return B + "models/%s/%s.geo.json" % (d, name)


def poser(d, name):
    return B + "posers/%s/%s.json" % (d, name)


def anim(d, name):
    return B + "animations/%s/%s.animation.json" % (d, name)


def resolver(d, sp):
    return B + "resolvers/%s/0_%s_base.json" % (d, sp)


def tex(d, name):
    return "assets/cobblemon/textures/pokemon/%s/%s.png" % (d, name)


def tex_id(d, name):
    return "cobblemon:textures/pokemon/%s/%s.png" % (d, name)


def poser_doc(group):
    return json.dumps({"portraitScale": 1, "poses": {"standing": {"animations": ["q.bedrock('%s', 'ground_idle')" % group]}}}).encode()


def resolver_doc(sp, variations):
    return json.dumps({"species": "cobblemon:" + sp, "order": 0, "variations": variations}).encode()


def base_variation(d, name, **kw):
    v = {"aspects": [], "poser": "cobblemon:" + name, "model": "cobblemon:%s.geo" % name, "texture": tex_id(d, name)}
    v.update(kw)
    return v


def zbytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in files.items():
            z.writestr(n, b if isinstance(b, bytes) else b.encode())
    return buf.getvalue()


def layer(label, files):
    return CMF.Layer(label, zipfile.ZipFile(io.BytesIO(zbytes(files))))


def stack(jar_files, *packs):
    """The jar lowest, then each (label, files) pack above it, in order."""
    jar_files = {"fabric.mod.json": '{"id": "cobblemon"}', **jar_files}
    return CMF.Stack([layer(JAR, jar_files)] + [layer(lbl, f) for lbl, f in packs], JAR)


# ------------------------------------------------------------------ rule 1: crash

PERSIAN = {"body": [(0, 0)], "head": [(8, 0)], "tail": [(16, 0)], "locator_mouth": []}
PERSIAN_JAR = {model("0053_persian", "persian_alolan"): geo(PERSIAN), POSER_CLASS % "PersianAlolan": b""}


def crash(jar_files, *packs):
    st = stack(jar_files, *packs)
    return CMF.crash_faults(st, CMF.builtin_poser_forms(st.layers[st.jar].zf))


def test_builtin_poser_forms_come_from_the_class_names():
    # without this, the crash rule has no built-in posers to check and reports nothing
    st = stack(PERSIAN_JAR)
    assert {"persian_alolan", "persianalolan"} <= CMF.builtin_poser_forms(st.layers[st.jar].zf)


def test_crash_flags_a_pack_model_missing_a_part_the_builtin_poser_needs():
    # without this, the Alolan Persian crash of 2026-09-14 ("Can't find part tail") goes undetected
    broken = {k: v for k, v in PERSIAN.items() if k != "tail"}
    f = crash(PERSIAN_JAR, ("Other.zip", {model("0053_persian", "persian_alolan"): geo(broken)}))
    assert [(x["form"], x["missing_parts"], x["pack"], x["root_missing"]) for x in f] == [
        ("persian_alolan", ["tail"], "Other.zip", False)]


def test_crash_marks_a_missing_root_part():
    # without this, the report cannot say the whole model is unusable when its first (root) part is gone
    broken = {k: v for k, v in PERSIAN.items() if k != "body"}
    f = crash(PERSIAN_JAR, ("Other.zip", {model("0053_persian", "persian_alolan"): geo(broken)}))
    assert f and f[0]["root_missing"] is True


@pytest.mark.parametrize("case", ["all_parts_and_more", "only_a_locator_missing", "json_poser_in_a_pack",
                                  "not_builtin", "not_overridden"])
def test_crash_does_not_flag_safe_forms(case):
    # without this, the crash list fills with forms that render fine and the real crashes are lost in it
    jar = dict(PERSIAN_JAR)
    pack = {}
    if case == "all_parts_and_more":
        pack[model("0053_persian", "persian_alolan")] = geo({**PERSIAN, "whiskers": [(24, 0)]})
    elif case == "only_a_locator_missing":
        pack[model("0053_persian", "persian_alolan")] = geo({k: v for k, v in PERSIAN.items() if k != "locator_mouth"})
    elif case == "json_poser_in_a_pack":
        pack[model("0053_persian", "persian_alolan")] = geo({"body": [(0, 0)]})
        pack[poser("0053_persian", "persian_alolan")] = poser_doc("persian_alolan")
    elif case == "not_builtin":
        del jar[POSER_CLASS % "PersianAlolan"]
        pack[model("0053_persian", "persian_alolan")] = geo({"body": [(0, 0)]})
    assert crash(jar, ("Other.zip", pack)) == []


# ------------------------------------------------------------------ rule 2: missing

VUL = "0629_vullaby"
VUL_FILES = {resolver(VUL, "vullaby"): resolver_doc("vullaby", [base_variation(VUL, "vullaby")]),
             model(VUL, "vullaby"): geo({"body": [(0, 0)]}), poser(VUL, "vullaby"): poser_doc("vullaby"),
             tex(VUL, "vullaby"): png(64, 64)}
SPAWNABLE = {"vullaby": ["data/spawns.json"]}


def missing(files, spawnable=SPAWNABLE, builtin=frozenset()):
    return CMF.missing_faults(stack(files), set(builtin), spawnable)


def test_missing_passes_a_complete_species():
    # without this, the rule could flag every spawnable species and the list would mean nothing
    assert missing(VUL_FILES) == []


@pytest.mark.parametrize("drop, problem", [
    ("resolver", "no resolver"),
    ("model", "model missing: cobblemon:vullaby.geo"),
    ("poser", "poser missing: cobblemon:vullaby"),
    ("texture", "texture missing: " + tex_id(VUL, "vullaby")),
])
def test_missing_flags_a_spawnable_species_without_a_complete_client_model(drop, problem):
    # without this, a species that spawns as the green substitute doll (Vullaby, Oranguru, 2026-09-26) passes
    path = {"resolver": resolver(VUL, "vullaby"), "model": model(VUL, "vullaby"), "poser": poser(VUL, "vullaby"),
            "texture": tex(VUL, "vullaby")}[drop]
    f = missing({k: v for k, v in VUL_FILES.items() if k != path})
    assert [(x["species"], x["problem"]) for x in f] == [("vullaby", [problem])]


def test_missing_accepts_a_builtin_poser():
    # without this, every species posed by a Kotlin class (no JSON poser) is reported missing
    files = {k: v for k, v in VUL_FILES.items() if k != poser(VUL, "vullaby")}
    assert missing(files, builtin={"vullaby"}) == []


def test_missing_flags_a_species_with_only_aspect_variations():
    # without this, a species whose resolver covers only shiny or regional forms renders its base form as the doll
    files = dict(VUL_FILES)
    files[resolver(VUL, "vullaby")] = resolver_doc("vullaby", [base_variation(VUL, "vullaby", aspects=["shiny"])])
    f = missing(files)
    assert len(f) == 1 and f[0]["problem"][0].startswith("no variation without aspects")


def test_missing_reports_only_spawnable_species():
    # without this, a broken model of a species that never spawns would be treated as a player-facing fault
    assert missing({}, spawnable={}) == []


# ------------------------------------------------------------------ rule 3: uv_mismatch

PID = "0018_pidgeot"
PID_BONES = {"body": [(0, 0), (8, 0)], "wing": [(16, 0), (24, 0)]}      # four UV rectangles


def pid_jar(**over):
    files = {resolver(PID, "pidgeot"): resolver_doc("pidgeot", [base_variation(PID, "pidgeot")]),
             model(PID, "pidgeot"): geo(PID_BONES), tex(PID, "pidgeot"): png(64, 64)}
    files.update(over)
    return files


def uv(jar_files, *packs):
    return {f["model"]: f for f in CMF.uv_forms(stack(jar_files, *packs))}


def test_uv_flags_a_pack_model_on_a_texture_drawn_for_another_layout():
    # without this, the scrambled Pidgeot and Talonflame of 2026-09-26 (pack model on Cobblemon's texture) pass
    f = uv(pid_jar(), ("Other.zip", {model(PID, "pidgeot"): geo({"body": [(32, 32), (40, 32)], "wing": [(48, 32)]})}))
    rec = f["cobblemon:pidgeot.geo"]
    assert rec["flagged"] and rec["uv_match"] == 0 and rec["model_pack"] == "Other.zip" and rec["texture_pack"] == JAR


@pytest.mark.parametrize("shared, total, flagged", [(2, 4, False), (1, 3, True), (3, 4, False), (0, 2, True)])
def test_uv_cut_is_under_half_of_the_models_rectangles(shared, total, flagged):
    # without this, the threshold can drift into either mode of the measured bimodal split (docstring: "under half")
    own = [(0, 0), (8, 0), (16, 0), (24, 0)][:shared]
    new = [(40 + 8 * i, 40) for i in range(total - shared)]
    f = uv(pid_jar(), ("Other.zip", {model(PID, "pidgeot"): geo({"body": own + new})}))
    rec = f["cobblemon:pidgeot.geo"]
    assert rec["uv_match"] == round(shared / total, 3) and rec["flagged"] is flagged


def test_uv_passes_a_pack_model_with_the_same_layout():
    # without this, every pack that re-rigs a model without touching its UVs is reported as broken
    same_uvs = {"root": [(0, 0), (8, 0)], "left_wing": [(16, 0)], "right_wing": [(24, 0)]}
    rec = uv(pid_jar(), ("Other.zip", {model(PID, "pidgeot"): geo(same_uvs)}))["cobblemon:pidgeot.geo"]
    assert rec["uv_match"] == 1.0 and not rec["flagged"]


def test_uv_compares_normalised_rectangles():
    # without this, a model re-declared in a larger UV space (the same layout, scaled) is flagged as a mismatch
    scaled = {n: [(u * 2, v * 2) for u, v in uvs] for n, uvs in PID_BONES.items()}
    rec = uv(pid_jar(), ("Other.zip", {model(PID, "pidgeot"): geo(scaled, 128, 128)}))["cobblemon:pidgeot.geo"]
    assert rec["uv_match"] == 1.0 and rec["aspect_ok"] and not rec["flagged"]


def test_uv_flags_a_texture_whose_aspect_ratio_differs_from_the_models_uv_space():
    # without this, the 128x64 snake textures on a 64x64 model (E19 Arbok) pass because the model itself is unchanged
    rec = uv(pid_jar(), ("Other.zip", {tex(PID, "pidgeot"): png(128, 64)}))["cobblemon:pidgeot.geo"]
    assert rec["uv_match"] == 1.0 and rec["aspect_ok"] is False and rec["flagged"]
    assert rec["texture_pack"] == "Other.zip" and rec["model_pack"] == JAR


def test_uv_ignores_a_form_whose_model_and_texture_come_from_one_pack():
    # without this, a pack's own consistent model and texture pair would be compared against Cobblemon's and flagged
    pack = {model(PID, "pidgeot"): geo({"body": [(32, 32)]}), tex(PID, "pidgeot"): png(64, 64)}
    assert "cobblemon:pidgeot.geo" not in uv(pid_jar(), ("Other.zip", pack))


# ------------------------------------------------------------------ an instance: scan and the server-pack build

class Instance:
    """options.txt, mods/<fake Cobblemon jar>, resourcepacks/Other.zip (breaks three forms), resourcepacks/<donor>."""
    PERSIAN_M = model("0053_persian", "persian_alolan")
    PID_ALT = model(PID + "_zz", "pidgeot")                # sorts after the jar's path, so it wins the id
    PID_P, PID_A = poser(PID, "pidgeot"), anim(PID, "pidgeot")
    VUL_FILES = {**VUL_FILES,
                 resolver(VUL, "vullaby"): resolver_doc("vullaby", [base_variation(VUL, "vullaby", layers=[
                     {"name": "emissive", "texture": tex_id(VUL, "vullaby_emissive")}])]),
                 anim(VUL, "vullaby"): b'{"animations": {"animation.vullaby.ground_idle": {}}}',
                 tex(VUL, "vullaby_emissive"): png(64, 64)}
    UNRELATED = {model("0151_mew", "mew"): geo({"body": [(0, 0)]}), tex("0151_mew", "mew"): png(64, 64)}

    def __init__(self, root: Path):
        self.root = root
        (root / "mods").mkdir(parents=True)
        (root / "resourcepacks").mkdir()
        (root / "options.txt").write_text('version:3955\nresourcePacks:["vanilla","fabric","file/Other.zip"]\n',
                                          encoding="utf-8")
        jar = {"fabric.mod.json": '{"id": "cobblemon"}', **PERSIAN_JAR, **pid_jar(),
               self.PID_P: poser_doc("pidgeot"), self.PID_A: b'{"animations": {"cobblemon": 1}}'}
        (root / "mods" / JAR_NAME).write_bytes(zbytes(jar))
        other = {"pack.mcmeta": '{"pack": {"pack_format": 34, "description": "other"}}',
                 self.PERSIAN_M: geo({"body": [(0, 0)], "head": [(8, 0)]}),
                 self.PID_ALT: geo({"body": [(32, 32), (40, 32)]}),
                 self.PID_P: poser_doc("pidgeot"), self.PID_A: b'{"animations": {"other": 1}}',
                 tex(VUL, "vullaby"): png(64, 64)}
        (root / "resourcepacks" / "Other.zip").write_bytes(zbytes(other))
        donor = {"pack.mcmeta": '{"pack": {"pack_format": 34, "description": "ATMxMSD RP Version 9.9.9"}}',
                 "readme.md": "# AllTheMons\n## Contributors:\n- Alice\n- Bob\n",
                 "LICENSE": "synthetic licence text\n", **self.VUL_FILES, **self.UNRELATED}
        self.donor = root / "resourcepacks" / CMF.DONOR_PACK
        self.donor.write_bytes(zbytes(donor))
        self.donor_files = donor

    COBBLEMON_FILES = {PERSIAN_M, PID_ALT, PID_P, PID_A}
    DONOR_PATHS = sorted(set(VUL_FILES))                   # six: resolver, model, poser, animation, two textures
    LEFT = {tex(VUL, "vullaby"): "Other.zip"}               # a pack above the donor ships it
    META = {"pack.mcmeta", "CREDITS.md", "LICENSE-AllTheMons.md", "cobblers-client-pack.json"}


@pytest.fixture
def instance(tmp_path, monkeypatch):
    spawns = tmp_path / "spawns.json"
    spawns.write_text(json.dumps({"entries": [{"pokemon": "vullaby"}]}), encoding="utf-8")
    order = tmp_path / "resourcepackoverrides.json"
    order.write_text(json.dumps({"default_packs": ["vanilla", "fabric", "file/" + CMF.DONOR_PACK, "file/Other.zip"]}),
                     encoding="utf-8")
    monkeypatch.setattr(CMF, "SPAWNS", spawns)
    monkeypatch.setattr(CMF, "BASE_PACK_ORDER", order)
    monkeypatch.setattr(CMF, "REPO", tmp_path)
    monkeypatch.setattr(CMF, "DONOR_PATHS", tmp_path / "manifest" / "client-pack-atm-subset.json")
    inst = Instance(tmp_path / "instance")
    yield inst
    for _, z, _ in CMF._MODS.pop(inst.root, []):
        z.close()


def test_the_instance_fixture_is_seen_by_the_stack(instance):
    # without this, the build tests below could pass on a stack that never read the fixture's packs
    st = CMF.stack_for(instance.root, include_ours=False)
    assert [l.label for l in st.layers] == [JAR, "Other.zip"]


def test_scan_flags_each_rule_and_the_built_pack_covers_them(instance, tmp_path):
    # without this, the pack could be built from a fault list that the scan does not agree it fixes
    before = CMF.scan(instance.root)
    assert before["uncovered"] == {"crash": ["persian_alolan"], "missing": ["vullaby"], "uv_mismatch": ["pidgeot"]}
    out = tmp_path / "out" / CMF.SERVER_PACK_NAME
    CMF.build_server_pack(instance.root, out)
    after = CMF.scan(instance.root, with_packs=[out])
    assert after["uncovered"] == {"crash": [], "missing": [], "uv_mismatch": []}


def test_server_pack_holds_exactly_the_derived_files_and_its_notices(instance, tmp_path):
    # without this, the pack can ship donor files the manifest does not list (the AllTheMons licence covers a subset)
    out = tmp_path / "out" / CMF.SERVER_PACK_NAME
    m = CMF.build_server_pack(instance.root, out)
    recorded = json.loads(CMF.DONOR_PATHS.read_text(encoding="utf-8"))
    assert recorded["paths"] == Instance.DONOR_PATHS and recorded["left_to_stack"] == Instance.LEFT
    assert recorded["species"] == ["vullaby"]
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
    donor_in_zip = set(recorded["paths"]) - set(recorded["left_to_stack"])
    assert names == Instance.COBBLEMON_FILES | donor_in_zip | Instance.META
    assert set(m["cobblemon_files"]) == Instance.COBBLEMON_FILES and set(m["donor_files"]) == donor_in_zip
    assert not any(n.startswith(tuple(Instance.UNRELATED)) for n in names)


def test_server_pack_copies_donor_and_cobblemon_files_unaltered(instance, tmp_path):
    # without this, the "unaltered subset" claim in the credits could be false, and a fix could carry a pack's bytes
    out = tmp_path / "out" / CMF.SERVER_PACK_NAME
    m = CMF.build_server_pack(instance.root, out)
    with zipfile.ZipFile(instance.root / "mods" / JAR_NAME) as jar, zipfile.ZipFile(out) as z:
        for n in m["donor_files"]:
            assert z.read(n) == instance.donor_files[n], n
        for dst, src in m["cobblemon_files"].items():
            assert z.read(dst) == jar.read(src), dst
    assert m["cobblemon_files"][Instance.PID_ALT] == model(PID, "pidgeot")


def test_server_pack_carries_the_donor_licence_and_credits(instance, tmp_path):
    # without this, the pack is redistributed without the attribution its donor's licence asks for
    out = tmp_path / "out" / CMF.SERVER_PACK_NAME
    CMF.build_server_pack(instance.root, out)
    with zipfile.ZipFile(out) as z:
        assert z.read("LICENSE-AllTheMons.md") == b"synthetic licence text\n"
        credits = z.read("CREDITS.md").decode("utf-8")
        mcmeta = json.loads(z.read("pack.mcmeta"))
    assert "- Alice" in credits and "- Bob" in credits and "9.9.9" in credits
    assert mcmeta["pack"]["pack_format"] == CMF.PACK_FORMAT
    assert mcmeta["credits"]["AllTheMons contributors"] == ["Alice", "Bob"]


def test_server_pack_build_is_deterministic(instance, tmp_path):
    # without this, the sha1 in server.properties changes on every rebuild and clients re-download an identical pack
    a, b = tmp_path / "a" / CMF.SERVER_PACK_NAME, tmp_path / "b" / CMF.SERVER_PACK_NAME
    CMF.build_server_pack(instance.root, a)
    for p in instance.root.rglob("*"):
        if p.is_file():
            os.utime(p, (1_900_000_000, 1_900_000_000))        # inputs touched: only content may matter
    CMF._MODS.pop(instance.root, None)
    m = CMF.build_server_pack(instance.root, b)
    assert a.read_bytes() == b.read_bytes()
    assert m["sha1"] == hashlib.sha1(b.read_bytes()).hexdigest()
    assert (b.parent / (b.name + ".sha1")).read_text(encoding="ascii").strip() == m["sha1"]
    with zipfile.ZipFile(b) as z:
        assert all(i.date_time == CMF.ZIP_DATE for i in z.infolist())
        assert z.namelist() == sorted(z.namelist())


def test_server_pack_build_refuses_a_subset_that_differs_from_the_committed_paths(instance, tmp_path):
    # without this, a changed donor or stack silently changes what the pack redistributes, unreviewed
    CMF.build_server_pack(instance.root, tmp_path / "first.zip")
    recorded = json.loads(CMF.DONOR_PATHS.read_text(encoding="utf-8"))
    recorded["paths"] = recorded["paths"][1:]
    CMF.DONOR_PATHS.write_text(json.dumps(recorded), encoding="utf-8")
    out = tmp_path / "second.zip"
    with pytest.raises(SystemExit) as e:
        CMF.build_server_pack(instance.root, out)
    assert "differs from" in str(e.value)
    assert not out.exists()
    assert json.loads(CMF.DONOR_PATHS.read_text(encoding="utf-8"))["paths"] == recorded["paths"]


def test_server_pack_build_refuses_a_missing_species_the_donor_cannot_supply(instance, tmp_path):
    # without this, the pack is published while a spawnable species still renders as the substitute doll
    CMF.SPAWNS.write_text(json.dumps({"entries": [{"pokemon": "vullaby"}, {"pokemon": "oranguru"}]}), encoding="utf-8")
    out = tmp_path / "out.zip"
    with pytest.raises(SystemExit) as e:
        CMF.build_server_pack(instance.root, out)
    assert "oranguru" in str(e.value)
    assert not out.exists()


@pytest.mark.xfail(strict=True, reason=(
    "tools/client_model_fix.py:764: build_server_pack compares only `paths` and `species` with the committed manifest, "
    "not `left_to_stack`. When a pack above the donor stops shipping a listed path, the build silently adds that donor "
    "file to the zip, and the committed manifest still says the file is left to the stack. The pack's content then "
    "differs from the reviewed record with no refusal (and no --record-paths)."))
def test_server_pack_build_refuses_when_what_it_ships_differs_from_the_committed_record(instance, tmp_path):
    # without this, the redistributed AllTheMons subset can grow without review while its path list stays the same
    CMF.build_server_pack(instance.root, tmp_path / "first.zip")
    recorded = json.loads(CMF.DONOR_PATHS.read_text(encoding="utf-8"))
    assert recorded["left_to_stack"] == Instance.LEFT
    other = instance.root / "resourcepacks" / "Other.zip"
    with zipfile.ZipFile(other) as z:
        kept = {n: z.read(n) for n in z.namelist() if n not in Instance.LEFT}
    other.write_bytes(zbytes(kept))
    out = tmp_path / "second.zip"
    try:
        CMF.build_server_pack(instance.root, out)
    except SystemExit:
        return
    with zipfile.ZipFile(out) as z:
        shipped = {n for n in z.namelist() if n in recorded["paths"]}
    assert shipped == set(recorded["paths"]) - set(recorded["left_to_stack"])


def test_install_puts_the_pack_on_top_once_and_keeps_the_first_backup(tmp_path):
    # without this, repeated local installs stack duplicate entries or overwrite the player's original options.txt
    inst = tmp_path / "instance"
    (inst / "resourcepacks").mkdir(parents=True)
    original = 'version:3955\nresourcePacks:["vanilla","fabric","file/X.zip"]\nlang:en_us\n'
    (inst / "options.txt").write_text(original, encoding="utf-8")
    z = tmp_path / CMF.PACK_NAME
    z.write_bytes(zbytes({"pack.mcmeta": "{}"}))
    CMF.install(inst, z)
    packs = CMF.install(inst, z)
    assert packs == ["vanilla", "fabric", "file/X.zip", "file/" + CMF.PACK_NAME]
    assert (inst / "options.txt.pre-cobblers-model-fixes").read_text(encoding="utf-8") == original
    assert "lang:en_us" in (inst / "options.txt").read_text(encoding="utf-8")
    assert (inst / "resourcepacks" / CMF.PACK_NAME).read_bytes() == z.read_bytes()


# ------------------------------------------------------------------ the committed path list

def test_the_committed_client_pack_path_list_is_well_formed():
    # without this, a hand edit to the manifest (unsorted, duplicated, outside assets/) makes every build refuse or
    # lets the recorded list name files the tool cannot have derived
    d = json.loads((ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json").read_text(encoding="utf-8"))
    paths = d["paths"]
    assert paths and paths == sorted(set(paths))
    assert all(p.startswith("assets/") and ("/bedrock/" in p or "/textures/" in p) for p in paths)
    assert set(d["left_to_stack"]) <= set(paths)
    assert d["species"] and d["species"] == sorted(set(d["species"]))
    assert d["source"] == CMF.DONOR_PACK and len(d["source_sha256"]) == 64
    int(d["source_sha256"], 16)
