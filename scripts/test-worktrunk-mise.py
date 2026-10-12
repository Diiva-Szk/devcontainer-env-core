#!/usr/bin/env python3
"""Exercise Worktrunk through real mise tasks and shims."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


SOURCE = Path(__file__).resolve().parents[1]
BASE = SOURCE / "docker-images/dev-base"
TOOL = "aqua:max-sixty/worktrunk"


class WorktrunkMiseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worktrunk-mise-test.")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "project with spaces"
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("MISE_", "WORKTRUNK_", "GIT_"))}
        system = self.base / "system"
        system.mkdir()
        source = tomllib.loads((BASE / "etc/mise/config.toml").read_text())
        # Keep the shipped task definitions; only Worktrunk is needed here.
        config = f'[settings]\nlocked = true\n[tools]\n"{TOOL}" = "{source["tools"][TOOL]}"\n'
        for name, task in source.get("tasks", {}).items():
            if name.startswith("wt:"):
                config += f'\n[tasks.{json.dumps(name)}]\n'
                config += ''.join(f'{key} = {json.dumps(value, ensure_ascii=False)}\n'
                                  for key, value in task.items())
        (system / "config.toml").write_text(config)
        shutil.copy(BASE / "etc/mise/mise.lock", system / "mise.lock")
        self.env.update(
            MISE_SYSTEM_CONFIG_DIR=str(system),
            MISE_GLOBAL_CONFIG_FILE=str(self.base / "global.toml"),
            MISE_DATA_DIR=str(self.base / "data"),
            MISE_STATE_DIR=str(self.base / "state"),
            MISE_SHIMS_DIR=str(self.base / "shims"),
            MISE_TRUSTED_CONFIG_PATHS=str(system),
            MISE_PARANOID="1",
            MISE_YES="0",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL="/dev/null",
            WORKTRUNK_CONFIG_PATH=str(self.base / "worktrunk-user.toml"),
            WORKTRUNK_SYSTEM_CONFIG_PATH=str(BASE / "etc/xdg/worktrunk/config.toml"),
        )
        # Register the already installed binary without downloading another copy.
        # A real mise shim is a symlink to mise, which dispatches by argv[0].
        self.run_cmd("mise", "link", f'{TOOL}@{source["tools"][TOOL]}', str(NATIVE.parent), cwd="/")
        shims = self.base / "shims"
        shims.mkdir(exist_ok=True)
        for name in ("wt", "git-wt"):
            (shims / name).symlink_to(shutil.which("mise"))
        self.env["PATH"] = f'{shims}:{self.env["PATH"]}'
        self.run_cmd("wt", "--version", cwd="/")
        self.run_cmd("git", "init", "-b", "main")
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "--allow-empty", "-m", "initial")

    def run_cmd(self, *args, cwd=None, success=True):
        result = subprocess.run(args, cwd=cwd or self.repo, env=self.env, text=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, f'{args}\n{result.stdout}\n{result.stderr}')
        else:
            self.assertNotEqual(result.returncode, 0, f'unexpected success: {args}')
        return result

    def test_tasks_forward_arguments_and_preserve_work(self):
        subdir = self.repo / "src"
        subdir.mkdir()
        self.run_cmd("mise", "run", "wt:add", "feat/mise", "--base", "HEAD", "--no-hooks", cwd=subdir)
        wt = self.repo / ".worktrees/feat-mise"
        self.assertTrue(wt.is_dir())
        self.assertFalse((subdir / ".worktrees").exists())
        self.run_cmd("mise", "run", "wt:switch", "feat/mise", "--no-hooks")
        listing = json.loads(self.run_cmd("mise", "run", "wt:list", "--format=json").stdout)
        self.assertIn(str(wt), [item["worktree"]["path"] for item in listing["items"]])
        help_text = self.run_cmd("mise", "run", "wt:switch", "--help").stdout
        self.assertIn("Usage: wt switch", help_text)
        (wt / "keep.txt").write_text("keep my work\n")
        self.run_cmd("mise", "run", "wt:rm", str(wt), "--no-hooks", success=False)
        self.assertEqual((wt / "keep.txt").read_text(), "keep my work\n")
        (wt / "keep.txt").unlink()
        self.run_cmd("mise", "run", "wt:rm", str(wt), "--no-delete-branch", "--no-hooks")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/mise")
        self.run_cmd("mise", "run", "wt:switch", "feat/mise", "--no-hooks")
        self.assertTrue(wt.is_dir())
        self.run_cmd("mise", "run", "wt:rm", "feat/mise", "--no-hooks")
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/mise", success=False)


if __name__ == "__main__":
    for tool in ("mise", "wt", "git"):
        if shutil.which(tool) is None:
            raise SystemExit(f"Required tool is missing: {tool}")
    # A container exposes wt through a shim; a host can put the release binary on PATH.
    resolved = subprocess.run(["mise", "which", "wt"], cwd="/", text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    NATIVE = Path(resolved.stdout.strip() if resolved.returncode == 0 else shutil.which("wt")).resolve()
    unittest.main(verbosity=2)
