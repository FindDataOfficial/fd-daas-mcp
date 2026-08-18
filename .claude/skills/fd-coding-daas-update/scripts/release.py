#!/usr/bin/env python3
"""fd-coding-daas-update release orchestrator.

Releases a new fd-daas-mcp version to GitHub + PyPI, end to end. Non-mutating
by default; requires --yes to push to GitHub and publish to PyPI.

Steps (each aborts the run on failure):
  1. pre-flight   - repo exists, gh authed, uv on PATH, PyPI token reachable
  2. version      - read current; compute next (--bump patch|minor|major, default
                    patch, or --version X.Y.Z)
  3. bump         - set version in pyproject.toml + insert CHANGELOG stub
  4. tests        - uv run pytest + python -m fd_daas_mcp.selfcheck
  5. build        - uv build + twine check dist/*
  6. fresh-verify - throwaway venv: pip install the wheel -> init + doctor (no env)
  7. confirm      - print plan; require --yes (or interactive yes) before mutating
  8. push         - commit version+changelog; git push origin HEAD:<default-branch>
  9. publish      - uv publish dist/* with UV_PUBLISH_TOKEN in the child env
                    (token from .env / env / ~/.zshrc, never printed)
 10. verify-live  - PyPI JSON shows the new version + fresh pip install -U + init

Usage:
  release.py [--bump patch|minor|major] [--version X.Y.Z] [--testpypi]
             [--skip-publish] [--yes] [--public-repo PATH]

Safety: without --yes, steps 1-6 run (all safe/read-only-ish: tests, build,
fresh-venv verify), then the script prints the planned push + publish and exits
without mutating. With --yes, steps 8-10 proceed after all checks pass.

The PyPI token is NEVER printed or passed as a CLI arg. The repo-root .env is
loaded first, then the token is read from UV_PUBLISH_TOKEN / PYPI_API_KEY (env,
incl. .env) or PYPI_API_KEY in ~/.zshrc, into memory and passed to uv publish
via the child process environment (UV_PUBLISH_TOKEN).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

# release.py -> scripts(0) -> fd-coding-daas-update(1) -> skills(2) -> .claude(3) -> repo root(4)
REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_dotenv() -> None:
    """Populate os.environ from the repo-root .env (does not override set vars).

    So FD_DAAS_MCP_PUBLIC_REPO / PYPI_API_KEY / UV_PUBLISH_TOKEN set in .env are
    honored, mirroring the rest of the skill scripts.
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

DEFAULT_PUBLIC_REPO = os.environ.get("FD_DAAS_MCP_PUBLIC_REPO") or str(
    Path.home() / "code" / "fd-daas-mcp-public"
)
PROXY = "http://127.0.0.1:7892"

# Phases that mutate the repo / external surfaces. Without --yes we stop before.
MUTATING_PHASES = ("push", "publish", "verify-live")


# ─────────────────────────────────────────────────────────────────────────────
# output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s

def info(msg: str) -> None:   print(f"{_c('36','›')} {msg}")
def ok(msg: str) -> None:     print(f"{_c('32','✓')} {msg}")
def warn(msg: str) -> None:   print(f"{_c('33','!')} {msg}")
def err(msg: str) -> None:    print(f"{_c('31','✗')} {msg}", file=sys.stderr)
def phase(n: int, name: str) -> None: print(f"\n{_c('1;37',f'[{n}/{10}] {name}')}")


class Abort(Exception):
    """Raised to stop the run before any mutating step."""


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command; on failure, print stderr + raise Abort (unless check=False)."""
    kw.setdefault("text", True)
    check = kw.pop("check", True)
    r = subprocess.run(cmd, capture_output=True, **kw)
    if check and r.returncode != 0:
        err(f"command failed: {' '.join(cmd)}")
        if r.stdout: sys.stderr.write(r.stdout)
        if r.stderr: sys.stderr.write(r.stderr)
        raise Abort()
    return r


# ─────────────────────────────────────────────────────────────────────────────
# token loading (never printed)
# ─────────────────────────────────────────────────────────────────────────────

def load_pypi_token() -> str | None:
    """Return the PyPI token from UV_PUBLISH_TOKEN / PYPI_API_KEY (env, incl. the
    repo-root .env loaded at startup) or PYPI_API_KEY in ~/.zshrc. The value is
    read into memory only - never printed, never logged.
    """
    t = os.environ.get("UV_PUBLISH_TOKEN") or os.environ.get("PYPI_API_KEY")
    if t:
        return t
    zshrc = Path.home() / ".zshrc"
    if not zshrc.exists():
        return None
    try:
        for line in zshrc.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s.startswith("export PYPI_API_KEY="):
                continue
            # Parse `export PYPI_API_KEY=value` or `export PYPI_API_KEY="value"`
            try:
                parts = shlex.split(s)  # ['export', 'PYPI_API_KEY=...']
                for p in parts[1:]:
                    if p.startswith("PYPI_API_KEY="):
                        return p[len("PYPI_API_KEY="):].strip()
            except ValueError:
                # shlex can choke on odd quoting; fall back to a naive split
                val = s[len("export PYPI_API_KEY="):].strip()
                return val.strip('"').strip("'")
    except OSError:
        return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# version + changelog
# ─────────────────────────────────────────────────────────────────────────────

def read_version(repo: Path) -> str:
    py = (repo / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', py, re.M)
    if not m:
        err("could not read version from pyproject.toml")
        raise Abort()
    return m.group(1)


def bump_version(current: str, kind: str) -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", current)
    if not m:
        err(f"unparseable version {current!r}")
        raise Abort()
    major, minor, patch = map(int, m.groups())
    if kind == "major":   return f"{major+1}.0.0"
    if kind == "minor":   return f"{major}.{minor+1}.0"
    if kind == "patch":   return f"{major}.{minor}.{patch+1}"
    err(f"unknown bump kind {kind!r}")
    raise Abort()


def write_version(repo: Path, new_v: str) -> None:
    py_path = repo / "pyproject.toml"
    py = py_path.read_text(encoding="utf-8")
    new = re.sub(r'(^version\s*=\s*)"[^"]+"', rf'\1"{new_v}"', py, count=1, flags=re.M)
    if new == py:
        err("version line not found in pyproject.toml")
        raise Abort()
    py_path.write_text(new, encoding="utf-8")


def add_changelog_stub(repo: Path, new_v: str) -> None:
    """Insert a `## [X.Y.Z] - YYYY-MM-DD` entry under `## [Unreleased]`."""
    cl = repo / "CHANGELOG.md"
    if not cl.exists():
        warn("no CHANGELOG.md - skipping changelog stub")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    text = cl.read_text(encoding="utf-8")
    needle = "## [Unreleased]"
    if needle not in text:
        warn("no `## [Unreleased]` section in CHANGELOG.md - skipping stub")
        return
    stub = (
        f"## [Unreleased]\n\n"
        f"## [{new_v}] - {today}\n\n"
        f"### Changed\n\n"
        f"- TODO: summarize changes since the last release (see `git log <prev-tag>..HEAD`).\n"
    )
    text = text.replace(needle, stub, 1)
    cl.write_text(text, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# fresh-venv install verify
# ─────────────────────────────────────────────────────────────────────────────

def _python_for_venv() -> str:
    return sys.executable


def fresh_venv_verify(repo: Path) -> None:
    """Install the built wheel into a throwaway venv and run init + doctor with
    DAAS_DATABASE_URL unset. Proves a real external user gets a working DB."""
    wheels = sorted((repo / "dist").glob("*.whl"))
    if not wheels:
        err("no wheel in dist/ - build step must run first")
        raise Abort()
    wheel = wheels[-1]
    with tempfile.TemporaryDirectory(prefix="fd-release-verify-") as td:
        tdp = Path(td)
        venv = tdp / "venv"
        run([_python_for_venv(), "-m", "venv", str(venv)])
        pip = venv / "bin" / "pip"
        fdmcp = venv / "bin" / "fd-daas-mcp"
        # install the local wheel (no extras, no src on path)
        run([str(pip), "install", "--quiet", str(wheel)], env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
        # run init + doctor from a fresh cwd with DAAS_DATABASE_URL unset
        work = tdp / "work"
        work.mkdir()
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("DAAS_DATABASE_URL", "DAAS_REGISTRY_DB")}
        r1 = subprocess.run([str(fdmcp), "init"], cwd=work, capture_output=True, text=True, env=clean_env)
        if r1.returncode != 0:
            err("fresh-venv `fd-daas-mcp init` failed:")
            sys.stderr.write(r1.stdout + r1.stderr)
            raise Abort()
        if not (work / "daas.db").exists():
            err("fresh-venv init did not create ./daas.db in cwd")
            raise Abort()
        r2 = subprocess.run([str(fdmcp), "doctor"], cwd=work, capture_output=True, text=True, env=clean_env)
        if r2.returncode != 0:
            err("fresh-venv `fd-daas-mcp doctor` exited non-zero")
            sys.stderr.write(r2.stdout + r2.stderr)
            raise Abort()
    ok(f"fresh-venv verify passed (pip install {wheel.name} -> init -> doctor)")


# ─────────────────────────────────────────────────────────────────────────────
# git + github
# ─────────────────────────────────────────────────────────────────────────────

def default_branch(repo: Path) -> str:
    r = run(["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"], cwd=repo)
    return r.stdout.strip() or "master"


def git_commit_push(repo: Path, new_v: str, default_br: str) -> None:
    msg = f"v{new_v}: release (see CHANGELOG)"
    run(["git", "add", "-A"], cwd=repo)
    # commit only if there is something staged
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False)
    if diff.returncode != 0:
        run(["git", "commit", "-q", "-m", msg], cwd=repo)
        ok(f"committed: {msg}")
    else:
        warn("nothing staged to commit (version+changelog already committed?)")
    # fast-forward the default branch to HEAD and push
    run(["git", "push", "origin", f"HEAD:{default_br}"], cwd=repo)
    ok(f"pushed to origin/{default_br}")


# ─────────────────────────────────────────────────────────────────────────────
# publish + verify-live
# ─────────────────────────────────────────────────────────────────────────────

def uv_publish(repo: Path, token: str, testpypi: bool) -> None:
    dist_files = [str(p) for p in sorted((repo / "dist").iterdir())
                  if p.suffix in (".whl", ".gz") and p.name.startswith("fd_daas_mcp-")]
    if not dist_files:
        err("no dist artifacts to publish")
        raise Abort()
    cmd = ["uv", "publish", *dist_files]
    if testpypi:
        cmd += ["--publish-url", "https://test.pypi.org/legacy/"]
    # token via child env (UV_PUBLISH_TOKEN) - NOT on the CLI, so ps can't see it.
    child_env = {**os.environ, "UV_PUBLISH_TOKEN": token}
    r = subprocess.run(cmd, cwd=repo, env=child_env)
    if r.returncode != 0:
        err("uv publish failed")
        raise Abort()
    target = "TestPyPI" if testpypi else "PyPI"
    ok(f"published {len(dist_files)} file(s) to {target}")


def _fetch_json(url: str) -> dict | None:
    """Fetch JSON from url; try direct, then via the local proxy. Returns None
    on failure (both attempts)."""
    headers = {"User-Agent": "fd-coding-daas-update"}
    for proxy in (None, PROXY):
        try:
            if proxy:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            continue
    return None


def verify_live(new_v: str, testpypi: bool) -> None:
    if testpypi:
        warn("skipping live verification for TestPyPI (propagation + index lag)")
        return
    # PyPI JSON: confirm the new version is the latest.
    data = _fetch_json("https://pypi.org/pypi/fd-daas-mcp/json")
    if data is None:
        warn("could not fetch PyPI JSON for verification - skipping the live-check")
    else:
        latest = data["info"]["version"]
        if latest == new_v:
            ok(f"PyPI latest is now {new_v}")
        else:
            warn(f"PyPI latest is {latest!r} (expected {new_v}) - propagation may be delayed; retry shortly.")
    # Fresh `pip install -U fd-daas-mcp` (from PyPI) + init + doctor.
    with tempfile.TemporaryDirectory(prefix="fd-release-live-") as td:
        venv = Path(td) / "venv"
        run([_python_for_venv(), "-m", "venv", str(venv)])
        pip = venv / "bin" / "pip"
        fdmcp = venv / "bin" / "fd-daas-mcp"
        run([str(pip), "install", "--quiet", "--upgrade", "fd-daas-mcp"],
            env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
        work = Path(td) / "work"
        work.mkdir()
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("DAAS_DATABASE_URL", "DAAS_REGISTRY_DB")}
        r1 = subprocess.run([str(fdmcp), "init"], cwd=work, capture_output=True, text=True, env=clean_env)
        r2 = subprocess.run([str(fdmcp), "doctor"], cwd=work, capture_output=True, text=True, env=clean_env)
        if r1.returncode == 0 and r2.returncode == 0:
            ok("live verify: pip install -U fd-daas-mcp -> init -> doctor OK")
        else:
            warn("live pip-install verify had issues (PyPI propagation lag? retry in a minute):")
            sys.stderr.write(r1.stdout + r1.stderr + r2.stdout + r2.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# pre-flight
# ─────────────────────────────────────────────────────────────────────────────

def preflight(repo: Path) -> None:
    if not (repo / "pyproject.toml").exists():
        err(f"not a fd-daas-mcp public repo (no pyproject.toml): {repo}")
        raise Abort()
    if not (repo / "src" / "fd_daas_mcp").exists():
        err(f"expected src/fd_daas_mcp/ under {repo}")
        raise Abort()
    for tool in ("gh", "uv", "git", "python3"):
        if not shutil.which(tool):
            err(f"required tool not on PATH: {tool}")
            raise Abort()
    # gh authed
    r = run(["gh", "auth", "status"], check=False)
    if r.returncode != 0:
        err("gh is not authenticated (run `gh auth login`)")
        raise Abort()
    # git status snapshot (informational)
    st = run(["git", "status", "--short"], cwd=repo, check=False).stdout.strip()
    if st:
        warn("public repo has uncommitted changes (will be included in the release commit):")
        for line in st.splitlines()[:15]:
            print(f"    {line}")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Release fd-daas-mcp to GitHub + PyPI.")
    ap.add_argument("--bump", choices=("patch", "minor", "major"), default="patch",
                    help="version bump kind (default: patch)")
    ap.add_argument("--version", help="explicit version (overrides --bump)")
    ap.add_argument("--testpypi", action="store_true", help="publish to TestPyPI instead of real PyPI")
    ap.add_argument("--skip-publish", action="store_true", help="push GitHub only, skip PyPI")
    ap.add_argument("--yes", action="store_true", help="proceed with push + publish without interactive confirm")
    ap.add_argument("--public-repo", default=DEFAULT_PUBLIC_REPO, help="path to the public repo")
    args = ap.parse_args()

    repo = Path(args.public_repo).expanduser().resolve()
    try:
        phase(1, "pre-flight")
        preflight(repo)
        ok(f"public repo: {repo}")

        phase(2, "version")
        cur = read_version(repo)
        new_v = args.version or bump_version(cur, args.bump)
        print(f"    {cur}  ->  {new_v}  ({'explicit' if args.version else args.bump + ' bump'})")

        # Token check (before mutating): confirm we CAN publish when the time comes.
        if not args.skip_publish:
            token = load_pypi_token()
            if token:
                ok(f"PyPI token reachable (length {len(token)}, value not shown)")
            else:
                err("no PyPI token found (UV_PUBLISH_TOKEN / PYPI_API_KEY in .env or env, or PYPI_API_KEY in ~/.zshrc)")
                err("set one: add `PYPI_API_KEY=pypi-...` to the repo-root .env (or `export PYPI_API_KEY=pypi-...` in ~/.zshrc), or pass UV_PUBLISH_TOKEN=...")
                raise Abort()

        phase(3, "bump version + changelog")
        # Save originals so a dry-run (no --yes) can restore them and leave the
        # repo clean. The bump is applied now so tests/build verify the *new*
        # version; it's reverted at the mutation gate if we stop.
        _py_path = repo / "pyproject.toml"
        _cl_path = repo / "CHANGELOG.md"
        _lock_path = repo / "uv.lock"
        _orig_py = _py_path.read_text(encoding="utf-8")
        _orig_cl = _cl_path.read_text(encoding="utf-8") if _cl_path.exists() else None
        _orig_lock = _lock_path.read_text(encoding="utf-8") if _lock_path.exists() else None
        write_version(repo, new_v)
        add_changelog_stub(repo, new_v)
        ok(f"pyproject.toml -> {new_v}; CHANGELOG stub added (fill the TODO from git log)")

        def _restore_bump() -> None:
            """Restore pyproject/CHANGELOG/uv.lock to their pre-bump state."""
            _py_path.write_text(_orig_py, encoding="utf-8")
            if _orig_cl is not None:
                _cl_path.write_text(_orig_cl, encoding="utf-8")
            if _orig_lock is not None:
                _lock_path.write_text(_orig_lock, encoding="utf-8")

        try:
            phase(4, "tests + selfcheck")
            run(["uv", "run", "pytest", "-q"], cwd=repo)
            ok("pytest passed")
            run(["uv", "run", "python", "-m", "fd_daas_mcp.selfcheck"], cwd=repo)
            ok("selfcheck passed")

            phase(5, "build + twine")
            # clean dist first for a reproducible build
            dist = repo / "dist"
            if dist.exists():
                shutil.rmtree(dist)
            run(["uv", "build"], cwd=repo)
            ok("built sdist + wheel")
            run(["uv", "run", "--with", "twine", "python", "-m", "twine", "check",
                 *map(str, sorted(dist.glob("fd_daas_mcp-*")))], cwd=repo)
            ok("twine check passed")

            phase(6, "fresh-venv install verify")
            fresh_venv_verify(repo)
        except Abort:
            # A check failed after the bump - restore so the repo stays clean.
            _restore_bump()
            err("aborted before completing the release (repo restored to pre-bump state).")
            return 1

        # ── mutation gate ───────────────────────────────────────────────────
        default_br = default_branch(repo)
        target = "TestPyPI" if args.testpypi else "PyPI"
        print()
        print(_c("1;37", "── release plan ──"))
        print(f"  version      : {cur} -> {new_v}")
        print(f"  github       : push origin HEAD:{default_br} (FindDataOfficial/fd-daas-mcp)")
        if args.skip_publish:
            print(f"  pypi         : SKIPPED (--skip-publish)")
        else:
            print(f"  pypi         : uv publish -> {target}")
            wheels = sorted(dist.glob("fd_daas_mcp-*"))
            print(f"  artifacts    : {', '.join(w.name for w in wheels)}")
        print()

        if not args.yes:
            # Dry-run: restore the version bump so the repo is clean.
            _restore_bump()
            if args.skip_publish:
                warn("DRY-RUN: tests + build + verify passed. Re-run with --yes to push to GitHub.")
            else:
                warn(f"DRY-RUN: tests + build + verify passed. Re-run with --yes to push GitHub + publish to {target}.")
                warn("PyPI upload is IRREVERSIBLE. Use --testpypi first if unsure.")
            return 0

        phase(8, f"push to GitHub (origin/{default_br})")
        git_commit_push(repo, new_v, default_br)

        if args.skip_publish:
            ok("done (GitHub only; PyPI skipped).")
            return 0

        phase(9, f"publish to {target}")
        uv_publish(repo, token, args.testpypi)

        phase(10, "verify live")
        verify_live(new_v, args.testpypi)

        print()
        ok(f"released fd-daas-mcp {new_v} to GitHub + {target}")
        if not args.testpypi:
            print(f"  https://pypi.org/project/fd-daas-mcp/{new_v}/")
        return 0

    except Abort:
        err("aborted before completing the release.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
