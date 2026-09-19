"""Does git's repository for a project belong to that project? (review of #250)

A `.git` FILE is how git links a directory to a repository kept elsewhere: a linked
worktree, a submodule, `--separate-git-dir`. It is also how a directory ends up pointing
at a repository that is not its own: a copy, a rename, a stale worktree. Every
borromeanRings project shares scaffold filenames, so a pointer to a sibling project
resolves some of its paths and a scan of "tracked files" reads the wrong project while
reporting a clean pass. Identity is decided by the pointer, not by overlapping names.
"""

import subprocess
from pathlib import Path

from meta_harness.repo_identity import foreign_repository


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "borromeanrings.toml").write_text("[checks]\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


def test_an_ordinary_repository_is_its_own(tmp_path: Path) -> None:
    assert foreign_repository(_repo(tmp_path / "proj")) == ""


def test_a_project_inside_a_larger_repository_is_git_discovery_as_usual(tmp_path: Path) -> None:
    mono = _repo(tmp_path / "mono")
    (mono / "packages" / "one").mkdir(parents=True)
    assert foreign_repository(mono / "packages" / "one") == ""


def test_a_linked_worktree_belongs_to_its_directory(tmp_path: Path) -> None:
    main = _repo(tmp_path / "main")
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt"))
    assert (tmp_path / "wt" / ".git").is_file()
    assert foreign_repository(tmp_path / "wt") == ""


def test_a_separate_git_dir_belongs_to_its_directory(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _git(proj, "init", "-q", f"--separate-git-dir={tmp_path / 'store.git'}")
    assert (proj / ".git").is_file()
    assert foreign_repository(proj) == ""


def test_a_pointer_to_a_sibling_projects_repository_is_foreign(tmp_path: Path) -> None:
    """The naive accident: both projects have borromeanrings.toml by construction."""
    sibling = _repo(tmp_path / "sibling")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "borromeanrings.toml").write_text("[checks]\n", encoding="utf-8")
    (proj / ".git").write_text(f"gitdir: {sibling / '.git'}\n", encoding="utf-8")
    reason = foreign_repository(proj)
    assert "not this project" in reason and str(sibling) in reason


def test_a_worktree_pointer_that_names_another_checkout_is_foreign(tmp_path: Path) -> None:
    main = _repo(tmp_path / "main")
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt"))
    impostor = tmp_path / "impostor"
    impostor.mkdir()
    (impostor / ".git").write_text((tmp_path / "wt" / ".git").read_text(), encoding="utf-8")
    assert "another checkout" in foreign_repository(impostor)


def test_a_dotgit_file_that_is_not_a_pointer_is_foreign(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").write_text("not a pointer\n", encoding="utf-8")
    assert "not a gitdir pointer" in foreign_repository(proj)


def test_a_submodule_belongs_to_its_directory(tmp_path: Path) -> None:
    upstream = _repo(tmp_path / "upstream")
    main = _repo(tmp_path / "main")
    _git(
        main,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(upstream),
        "vendor/up",
    )
    sub = main / "vendor" / "up"
    assert (sub / ".git").is_file()
    assert foreign_repository(sub) == ""


def test_an_undecodable_dotgit_file_is_refused_not_guessed(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").write_bytes(b"gitdir: \xff\xfe\n")
    assert "cannot read" in foreign_repository(proj)


def test_an_undecodable_worktree_backlink_is_refused_not_guessed(tmp_path: Path) -> None:
    main = _repo(tmp_path / "main")
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt"))
    gitdir = Path((tmp_path / "wt" / ".git").read_text().split(":", 1)[1].strip())
    (gitdir / "gitdir").write_bytes(b"\xff\xfe\n")
    assert "cannot read" in foreign_repository(tmp_path / "wt")


def test_a_dangling_pointer_is_left_to_git_which_refuses_it(tmp_path: Path) -> None:
    """A pointer to nothing names no other project's files, so identity has nothing to
    object to; git itself then reports "not a git repository" and 12_secrets fails closed
    on that (its own guard, before identity is consulted)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").write_text(f"gitdir: {tmp_path / 'gone.git'}\n", encoding="utf-8")
    assert foreign_repository(proj) == ""
    inside = subprocess.run(
        ["git", "-C", str(proj), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        check=False,
    )
    assert inside.returncode != 0
