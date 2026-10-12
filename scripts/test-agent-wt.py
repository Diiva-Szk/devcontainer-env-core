#!/usr/bin/env python3
"""Run Worktrunk and the shipped DAGs with real CLIs in temporary repos."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
AGENT = SOURCE / "docker-images/ai/opt/agent-wt"


class AgentWorktreeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-wt-test.")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("LMM_", "DAGU_", "GIT_", "WORKTRUNK_"))}
        self.env.update(
            PATH=f"{AGENT / 'bin'}:{SOURCE / 'docker-images/dev-base/usr/local/bin'}:{os.environ['PATH']}",
            DAGU_HOME=str(self.base / "dagu"),
            DAGU_DAGS_DIR=str(self.base / "dags"),
            DAGU_SKIP_EXAMPLES="true",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL="/dev/null",
            WORKTRUNK_CONFIG_PATH=str(self.base / "worktrunk-user.toml"),
            WORKTRUNK_SYSTEM_CONFIG_PATH=str(SOURCE / "docker-images/dev-base/etc/xdg/worktrunk/config.toml"),
        )
        (self.base / "dags").mkdir()
        for dag in (AGENT / "dags").glob("*.yaml"):
            # Only the image's immutable template path is relocated for host-side tests.
            (self.base / "dags" / dag.name).write_text(
                dag.read_text().replace("/opt/agent-wt/template", str(AGENT / "template"))
            )
        self.repo = self.new_repo("project with spaces")
        self.dag("init")

    def run_cmd(self, *args, cwd=None, success=True, env=None):
        cwd = cwd or self.repo
        result = subprocess.run(
            args, cwd=cwd, env={**self.env, "PWD": str(cwd), **(env or {})},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
        )
        if success:
            self.assertEqual(result.returncode, 0, f"{args}\n{result.stdout}")
        else:
            self.assertNotEqual(result.returncode, 0, f"unexpected success: {args}")
        return result.stdout.strip()

    def new_repo(self, name):
        repo = self.base / name
        repo.mkdir(parents=True)
        self.run_cmd("git", "init", "-b", "main", cwd=repo)
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "--allow-empty", "-m", "initial", cwd=repo)
        return repo

    def dag(self, action, *params, cwd=None, success=True):
        output = self.run_cmd("dagu", "start", f"agent-wt-{action}", "--", *params,
                              cwd=cwd, success=success)
        # Empty directories do not appear in git status, so check the filesystem too.
        literals = [str(p.relative_to(self.base)) for p in self.base.rglob("*") if "${PWD}" in p.name]
        self.assertEqual(literals, [], "Dagu created a literal ${PWD} directory")
        return output

    def create(self, name="login-coder", *params):
        self.dag("create", f"NAME={name}", *params)
        return self.repo / ".worktrees" / name

    def draft(self, cwd, body):
        path = Path(self.run_cmd("lmm", "draft", "-s", "test", cwd=cwd))
        with (path / "index.md").open("a") as file:
            file.write(body)
        return path

    def test_configuration_and_round_trip(self):
        wt = self.create()
        self.assertTrue((wt / "CLAUDE.md").is_file())
        settings = json.loads((wt / ".claude/settings.json").read_text())
        self.assertEqual(settings["model"], "claude-opus-5-5")
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=wt), "")
        draft = self.draft(self.repo, "implement this\n")
        message_id = self.run_cmd("lmm", "post", "-t", "login-coder", str(draft)).split(" ", 1)[0]
        nested = wt / "src"
        nested.mkdir()
        received = Path(self.run_cmd("lmm", "receive", cwd=nested))
        message = json.loads(self.run_cmd("lmm", "show", str(received), "--json", cwd=wt))
        self.assertEqual(message["frontmatter"]["lmm_from"], "root")
        self.assertIn("implement this", message["body"])
        self.assertEqual(received.parent, wt / ".lmm-inbox/login-coder")
        reply = self.draft(nested, "done\n")
        self.run_cmd("lmm", "post", "--reply", str(received), str(reply), cwd=nested)
        response = self.run_cmd("lmm", "wait", "--in-reply-to", message_id, "--timeout", "1")
        response_doc = json.loads(self.run_cmd("lmm", "show", response, "--json"))
        self.assertEqual(response_doc["frontmatter"]["lmm_from"], "login-coder")
        self.assertEqual(response_doc["frontmatter"]["lmm_to"], "root")
        # Unsolicited reports also use root without -t or --reply.
        report = self.draft(wt, "report\n")
        self.run_cmd("lmm", "post", str(report), cwd=wt)
        self.assertTrue(self.run_cmd("lmm", "receive"))
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=wt), "")

    def test_profiles_excludes_and_mail_survive_removal(self):
        first = self.create()
        second = self.create("another-coder", "ROLE=coder", "PROFILE=claude-opus5.5")
        codex = self.create("codex-coder", "ROLE=coder", "PROFILE=codex-astra6")
        self.assertTrue((codex / "AGENTS.md").is_file())
        self.assertIn('model = "astra6"', (codex / ".codex/config.toml").read_text())
        pending = self.draft(self.repo, "keep this\n")
        self.run_cmd("lmm", "post", "-t", "login-coder", str(pending))
        (first / "user-change.txt").write_text("keep me")
        self.dag("remove", "NAME=login-coder", success=False)
        self.assertTrue(first.exists())
        (first / "user-change.txt").unlink()
        self.dag("remove", "NAME=login-coder")
        self.assertFalse(first.exists())
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=second), "")
        self.assertIn("new=1", self.run_cmd("lmm", "box", "list"))
        self.create()
        self.assertIn("keep this", (Path(self.run_cmd("lmm", "receive", cwd=first)) / "index.md").read_text())

    def test_project_isolation_and_explicit_repo(self):
        first = self.create()
        other = self.new_repo("other-project")
        self.dag("init", f"REPO={other}")
        self.dag("create", "NAME=login-coder", f"REPO={other}")
        self.run_cmd("lmm", "post", "-t", "login-coder", str(self.draft(self.repo, "private\n")))
        self.assertEqual(self.run_cmd("lmm", "receive", cwd=other / ".worktrees/login-coder"), "")
        self.assertTrue(self.run_cmd("lmm", "receive", cwd=first))
        # Explicit environment settings retain the native CLI's semantics.
        self.assertIn("new=0", self.run_cmd("lmm", "box", "list", cwd=other,
                          env={"LMM_HOME": str(self.repo / ".git/agent-wt/lmm")}))

    def test_deep_project_root_and_subdirectory(self):
        # Keep the exact example path supplied by the user as a regression case.
        repo = self.new_repo("work/GitHub/org_name/my-projet")
        self.dag("init", cwd=repo)
        subdir = repo / "src"
        subdir.mkdir()
        self.dag("init", cwd=subdir)
        self.dag("create", "NAME=login-coder", cwd=subdir)
        wt = repo / ".worktrees/login-coder"
        self.assertTrue((wt / "CLAUDE.md").is_file())
        self.assertFalse((subdir / ".agent-wt").exists())
        self.assertFalse((subdir / ".worktrees").exists())
        self.dag("remove", "NAME=login-coder", cwd=subdir)
        self.assertFalse(wt.exists())

    def test_dotted_name_removal_preserves_other_exclude_blocks(self):
        self.create("a.b", "ROLE=coder", "PROFILE=claude-opus5.5")
        other = self.create("axb", "ROLE=coder", "PROFILE=codex-astra6")
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=other), "")
        self.dag("remove", "NAME=a.b")
        exclude = (self.repo / ".git/info/exclude").read_text()
        self.assertNotIn("# >>> agent-wt:a.b", exclude)
        self.assertIn("# >>> agent-wt:axb", exclude)
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=other), "")
        self.dag("remove", "NAME=axb")
        self.assertFalse(other.exists())

    def test_drafts_are_protected_and_force_preserves_mail_originals(self):
        wt = self.create()
        request = self.draft(self.repo, "task\n")
        message_id = self.run_cmd("lmm", "post", "-t", "login-coder", str(request)).split(" ", 1)[0]
        received = Path(self.run_cmd("lmm", "receive", cwd=wt))
        draft = self.draft(wt, "unfinished report\n")
        original = (draft / "index.md").read_text()
        exclude = (self.repo / ".git/info/exclude").read_text()
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=wt), "")
        output = self.dag("remove", "NAME=login-coder", "DELETE_BRANCH=true", success=False)
        self.assertIn("下書きが残っているため削除しません", output)
        self.assertIn("DISCARD_DRAFTS=true", output)
        self.assertNotIn("FORCE=true", output)
        self.assertEqual((draft / "index.md").read_text(), original)
        self.assertEqual((self.repo / ".git/info/exclude").read_text(), exclude)
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login")
        self.assertTrue(received.exists())
        self.dag("remove", "NAME=login-coder", "DELETE_BRANCH=true", "FORCE=true")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login", success=False)
        self.assertIn("task", self.run_cmd("lmm", "show", "--id", message_id,
                                           env={"LMM_NAME": "login-coder"}))

    def test_discard_drafts_removes_clean_worktree(self):
        wt = self.create()
        draft = self.draft(wt, "finished report\n")
        self.run_cmd("lmm", "post", str(draft), cwd=wt)
        self.dag("remove", "NAME=login-coder", "DISCARD_DRAFTS=true", "DELETE_BRANCH=true")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login", success=False)
        self.assertNotIn("# >>> agent-wt:login-coder", (self.repo / ".git/info/exclude").read_text())
        received = Path(self.run_cmd("lmm", "receive"))
        self.assertIn("finished report", (received / "index.md").read_text())

    def test_discard_drafts_preserves_dirty_worktree_and_unmerged_branch(self):
        wt = self.create()
        app = wt / "app.txt"
        app.write_text("unmerged work\n")
        self.run_cmd("git", "add", "app.txt", cwd=wt)
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-m", "unmerged work", cwd=wt)
        tip = self.run_cmd("git", "rev-parse", "HEAD", cwd=wt)
        app.write_text("uncommitted work\n")
        draft = self.draft(wt, "finished report\n")
        self.run_cmd("lmm", "post", str(draft), cwd=wt)
        original = (draft / "index.md").read_text()
        exclude = (self.repo / ".git/info/exclude").read_text()

        # Branch deletion must reject unmerged commits. Keeping the branch must
        # still reject the dirty worktree, even when discarding drafts is allowed.
        for delete_branch in ("true", "false"):
            with self.subTest(delete_branch=delete_branch):
                output = self.dag("remove", "NAME=login-coder", "DISCARD_DRAFTS=true",
                                  f"DELETE_BRANCH={delete_branch}", success=False)
                self.assertNotIn("下書きが残っているため削除しません", output)
                if delete_branch == "true":
                    self.assertIn("未マージのコミット", output)
                self.assertIn("M app.txt", output)
                self.assertEqual(app.read_text(), "uncommitted work\n")
                self.assertEqual((draft / "index.md").read_text(), original)
                self.assertEqual((self.repo / ".git/info/exclude").read_text(), exclude)
                self.assertEqual(self.run_cmd("git", "rev-parse", "refs/heads/feat/login"), tip)

    def test_removal_after_cleaning_up_sent_drafts(self):
        wt = self.create()
        draft = self.draft(wt, "finished report\n")
        self.run_cmd("lmm", "post", str(draft), cwd=wt)
        self.dag("remove", "NAME=login-coder", success=False)
        self.assertTrue(draft.exists(), "sent drafts are protected too")
        shutil.rmtree(draft)
        self.assertTrue((wt / ".lmm-drafts/.gitignore").is_file())
        self.dag("remove", "NAME=login-coder")
        self.assertFalse(wt.exists(), "empty draft directories and .gitignore must not block removal")

    def test_removal_with_brackets_in_project_path(self):
        self.repo = self.new_repo("project [old]")
        self.dag("init")
        wt = self.create()
        draft = self.draft(wt, "finished report\n")
        self.run_cmd("lmm", "post", str(draft), cwd=wt)
        self.dag("remove", "NAME=login-coder", success=False)
        shutil.rmtree(draft)
        self.assertTrue((wt / ".lmm-drafts/.gitignore").is_file())
        self.dag("remove", "NAME=login-coder")
        self.assertFalse(wt.exists())

    def test_invalid_names_and_existing_worktree_are_preserved(self):
        for name in ("root", "lmm", "Uppercase", "../escape", "x" * 65):
            self.dag("create", f"NAME={name}", "ROLE=coder", "PROFILE=claude-opus5.5", success=False)
        wt = self.create()
        (wt / "keep.txt").write_text("keep")
        self.dag("create", "NAME=login-coder", success=False)
        self.assertEqual((wt / "keep.txt").read_text(), "keep")
        self.dag("init", cwd=wt, success=False)
        self.assertFalse((wt / ".agent-wt").exists())

    def test_worktrunk_commands_and_bash_directory_switch(self):
        integration = SOURCE / "docker-images/dev-base/etc/bash/worktrunk.sh"
        # The host need not have the image's profile script installed.
        init = self.base / "worktrunk.sh"
        init.write_text(integration.read_text().replace(
            "/etc/profile.d/mise.sh", str(SOURCE / "docker-images/dev-base/etc/profile.d/mise.sh")))
        output = self.run_cmd("bash", "--noprofile", "--norc", "-eic",
            'source "$1"; wt switch --create feat/shell --no-hooks; printf "\\nWT_CWD=%s\\n" "$PWD"; '
            'wt switch main --no-hooks; printf "\\nROOT_CWD=%s\\n" "$PWD"', "bash", str(init),
            env={"WORKTRUNK_BIN": shutil.which("wt")})
        wt = self.repo / ".worktrees/feat-shell"
        self.assertIn(f"WT_CWD={wt}\n", output)
        self.assertIn(f"ROOT_CWD={self.repo}", output)
        listing = json.loads(self.run_cmd("wt", "list", "--format=json"))
        paths = {item["worktree"]["path"] for item in listing["items"] if "worktree" in item}
        self.assertIn(str(wt), paths)
        self.run_cmd("wt", "remove", "--foreground", "--no-hooks", "feat/shell")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/shell", success=False)

    def test_branch_in_another_worktree_is_preserved(self):
        other = self.repo / ".worktrees/external"
        self.run_cmd("git", "worktree", "add", "-b", "external", str(other))
        (other / "CLAUDE.md").write_text("keep existing rules\n")
        (other / "user-change.txt").write_text("keep existing work\n")
        output = self.dag("create", "NAME=login-coder", "BRANCH=external", success=False)
        self.assertIn("既に worktree で使われているブランチ", output)
        self.assertEqual((other / "CLAUDE.md").read_text(), "keep existing rules\n")
        self.assertEqual((other / "user-change.txt").read_text(), "keep existing work\n")
        self.assertFalse((self.repo / ".worktrees/login-coder").exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/external")

    def test_origin_branch_is_tracked_and_existing_branch_is_reused(self):
        remote = self.new_repo("origin")
        (remote / "remote.txt").write_text("remote work\n")
        self.run_cmd("git", "add", "remote.txt", cwd=remote)
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-m", "remote work", cwd=remote)
        self.run_cmd("git", "branch", "feat/login", cwd=remote)
        self.run_cmd("git", "remote", "add", "origin", str(remote))
        self.run_cmd("git", "fetch", "origin")
        wt = self.create()
        self.assertEqual((wt / "remote.txt").read_text(), "remote work\n")
        self.assertEqual(self.run_cmd("git", "rev-parse", "--abbrev-ref", "@{upstream}", cwd=wt),
                         "origin/feat/login")
        # The branch is merged into its upstream but not the main worktree's HEAD.
        self.dag("remove", "NAME=login-coder", "DELETE_BRANCH=true")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login", success=False)
        self.run_cmd("git", "branch", "existing")
        wt = self.create("login-coder", "BRANCH=existing", "BASE=not-a-ref")
        self.assertEqual(self.run_cmd("git", "branch", "--show-current", cwd=wt), "existing")

    def test_dag_skips_worktrunk_hooks_and_overrides_path_settings(self):
        (self.base / "worktrunk-user.toml").write_text(
            'worktree-path = "../elsewhere/{{ branch | sanitize }}"\n'
            'pre-start = "touch user-hook-ran"\n')
        config = self.repo / ".config/wt.toml"
        config.parent.mkdir()
        config.write_text('pre-start = "touch project-hook-ran"\n'
                          'pre-remove = "exit 71"\n')
        self.run_cmd("git", "add", ".config/wt.toml")
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-m", "project hooks")
        wt = self.create()
        self.assertTrue((wt / "CLAUDE.md").is_file())
        for marker in ("user-hook-ran", "project-hook-ran"):
            self.assertEqual(list(self.base.rglob(marker)), [])
        self.dag("remove", "NAME=login-coder")
        self.assertFalse(wt.exists())
        self.assertFalse((self.base / "elsewhere").exists())

    def test_removal_uses_current_branch_after_switch(self):
        wt = self.create()
        self.run_cmd("git", "switch", "-c", "changed", cwd=wt)
        self.dag("remove", "NAME=login-coder", "DELETE_BRANCH=true")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login")
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/changed", success=False)

    def test_detached_worktree_removal_keeps_original_branch(self):
        wt = self.create()
        self.run_cmd("git", "switch", "--detach", cwd=wt)
        self.dag("remove", "NAME=login-coder", "DELETE_BRANCH=true")
        self.assertFalse(wt.exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/feat/login")

    def test_generation_failure_rolls_back_only_new_work(self):
        other = self.create("axb", "ROLE=coder", "PROFILE=codex-astra6")
        profile = self.repo / ".agent-wt/profiles/broken"
        profile.mkdir()
        (profile / "rulesync.jsonc").write_text('{"targets": ["does-not-exist"]}')
        self.dag("create", "NAME=a.b", "ROLE=coder", "PROFILE=broken", success=False)
        self.assertFalse((self.repo / ".worktrees/a.b").exists())
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/agent/a.b", success=False)
        self.run_cmd("git", "branch", "existing")
        self.dag("create", "NAME=a.b", "ROLE=coder", "PROFILE=broken", "BRANCH=existing", success=False)
        self.run_cmd("git", "show-ref", "--verify", "refs/heads/existing")
        self.assertIn("# >>> agent-wt:axb", (self.repo / ".git/info/exclude").read_text())
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=other), "")
        self.dag("remove", "NAME=axb")

    def test_init_preserves_custom_settings_and_tracked_configs(self):
        spec = self.repo / ".agent-wt/worktrees.yaml"
        before = spec.read_text() + "# local customization\n"
        spec.write_text(before)
        self.dag("init")
        self.assertEqual(spec.read_text(), before)
        (self.repo / "CLAUDE.md").write_text("project rules\n")
        self.run_cmd("git", "add", "CLAUDE.md")
        self.run_cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-m", "project rules")
        wt = self.create()
        self.assertIn("Role: coder", (wt / "CLAUDE.md").read_text())
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "project rules\n")
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=wt), "")


if __name__ == "__main__":
    for tool in ("dagu", "rulesync", "lmm-native", "yq", "git", "wt"):
        if shutil.which(tool) is None:
            raise SystemExit(f"Required tool is missing: {tool}")
    unittest.main(verbosity=2)
