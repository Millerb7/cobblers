import re

# The Minecraft EULA is a human decision. No tracked or to-be-tracked file may
# accept it. The pattern is built from parts so this test file itself passes.
FORBIDDEN = re.compile(r"eula" + r"\s*=\s*" + r"true", re.IGNORECASE)
TEXT_SUFFIXES = {".txt", ".md", ".json", ".json5", ".toml", ".properties", ".ps1", ".py", ".cfg", ".yml", ".yaml", ".sh", ".bat", ".cmd", ".example", ""}


def test_no_eula(tracked_files):
    offenders = []
    for p in tracked_files:
        if p.suffix.lower() not in TEXT_SUFFIXES or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if FORBIDDEN.search(text):
            offenders.append(str(p))
    assert not offenders, f"files accepting the EULA: {offenders}"


def test_no_eula_file_tracked(tracked_files):
    assert not [p for p in tracked_files if p.name.lower() == "eula.txt"]
