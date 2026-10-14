"""Active runtime config classification for GET /runtime/status (issue #315)."""

from pathlib import Path

from app.services.runtime_status_service import classify_active_release


def _release(root: Path, name: str, *, coraza_spoa_yaml: bool) -> Path:
    release = root / "releases" / name
    release.mkdir(parents=True)
    (release / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    if coraza_spoa_yaml:
        (release / "coraza-spoa.yaml").write_text(
            "applications: []\n", encoding="utf-8"
        )
    return release


def test_missing_current_is_reported_as_missing(tmp_path: Path) -> None:
    assert classify_active_release(tmp_path / "current") == ("missing", "fallback")


def test_generated_release_is_reported_as_generated(tmp_path: Path) -> None:
    _release(tmp_path, "abc", coraza_spoa_yaml=True)
    (tmp_path / "current").symlink_to("releases/abc")

    assert classify_active_release(tmp_path / "current") == (
        "generated",
        "generated",
    )


def test_seed_release_is_reported_as_seed(tmp_path: Path) -> None:
    _release(tmp_path, "seed", coraza_spoa_yaml=False)
    (tmp_path / "current").symlink_to("releases/seed")

    assert classify_active_release(tmp_path / "current") == ("seed", "fallback")


def test_applied_release_without_coraza_yaml_uses_the_coraza_fallback(
    tmp_path: Path,
) -> None:
    """A release from before per-policy applications still runs Coraza on the
    single application baked into the image."""
    _release(tmp_path, "previous", coraza_spoa_yaml=False)
    (tmp_path / "current").symlink_to("releases/previous")

    assert classify_active_release(tmp_path / "current") == (
        "generated",
        "fallback",
    )


def test_broken_symlink_is_reported_as_missing(tmp_path: Path) -> None:
    (tmp_path / "current").symlink_to("releases/gone")

    assert classify_active_release(tmp_path / "current") == ("missing", "fallback")
