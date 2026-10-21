"""The backup refuses a stale manifest instead of passing over the gap (P139)."""

import pytest

from scripts import backup_models as bm


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for name, content in (("models/mfstnet/a.pt", b"a"), ("models/ppo/p.zip", b"p"),
                          ("models/detector/d.pt", b"d")):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    monkeypatch.setattr(bm, "ROOT", tmp_path)
    monkeypatch.setattr(bm, "MANIFEST", tmp_path / "model_artifacts.sha256")
    monkeypatch.setattr(bm, "same_physical_disk", lambda dest: False)
    bm.write_manifest()
    return tmp_path


def test_every_source_directory_is_covered(repo):
    assert set(bm.read_manifest(bm.MANIFEST)) == {
        "models/mfstnet/a.pt", "models/ppo/p.zip", "models/detector/d.pt"}


def test_a_fresh_manifest_passes_the_check(repo):
    assert bm.check() == 0


@pytest.mark.parametrize("change, kind", [
    (lambda root: (root / "models/ppo/new.zip").write_bytes(b"n"), "not in manifest"),
    (lambda root: (root / "models/detector/d.pt").unlink(), "gone from disk"),
    (lambda root: (root / "models/mfstnet/a.pt").write_bytes(b"changed"), "hash changed"),
])
def test_each_kind_of_staleness_is_named(repo, change, kind):
    change(repo)
    problems = bm.stale(bm.read_manifest(bm.MANIFEST))
    assert [k for k, names in problems.items() if names] == [kind]
    assert bm.check() == 1


def test_pack_refuses_a_stale_manifest_and_copies_nothing(repo, tmp_path_factory):
    (repo / "models/ppo/new.zip").write_bytes(b"n")
    dest = tmp_path_factory.mktemp("drive")
    assert bm.pack(dest) == 1
    assert not any(dest.iterdir())


def test_pack_copies_and_verifies_a_current_manifest(repo, tmp_path_factory):
    dest = tmp_path_factory.mktemp("drive")
    assert bm.pack(dest) == 0
    assert (dest / "models/ppo/p.zip").read_bytes() == b"p"
    assert bm.verify(dest) == 0


def test_a_regenerated_manifest_does_not_silently_drop_a_recorded_artifact(repo):
    before = bm.MANIFEST.read_bytes()
    (repo / "models/ppo/p.zip").unlink()
    assert bm.write_manifest() == 1
    assert bm.MANIFEST.read_bytes() == before
    assert bm.write_manifest(frozenset({"models/ppo/p.zip"})) == 0
    assert "models/ppo/p.zip" not in bm.read_manifest(bm.MANIFEST)


@pytest.mark.parametrize("damage", [
    lambda dest: (dest / "models/ppo/p.zip").unlink(),
    lambda dest: (dest / "models/ppo/p.zip").write_bytes(b"corrupt"),
    lambda dest: (dest / "models/ppo/extra.zip").write_bytes(b"x"),
    lambda dest: (dest / "model_artifacts.sha256").write_text("# other\n"),
])
def test_verify_fails_on_missing_corrupt_or_unexpected_files(repo, tmp_path_factory, damage):
    dest = tmp_path_factory.mktemp("drive")
    assert bm.pack(dest) == 0
    damage(dest)
    assert bm.verify(dest) == 1
