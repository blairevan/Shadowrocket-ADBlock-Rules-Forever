"""Exercise the real release step without network access or publishing."""

from pathlib import Path
import os
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
RULES = (
    "DOMAIN-SUFFIX,xiaoyuzhoufm.com,DIRECT",
    "DOMAIN-SUFFIX,xyzcdn.net,DIRECT",
)


def release_step(name="Keep Xiaoyuzhou connections direct"):
    """Read a release shell block without executing unrelated workflow steps."""
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    section = workflow.split("      - name: " + name + "\n", 1)[1]
    section = section.split("\n      - name:", 1)[0].split("        run: |\n", 1)[1]
    return textwrap.dedent(section)


class XiaoyuzhouRulesTests(unittest.TestCase):
    """Check rule priority, preservation, repeatability, and failure behavior."""

    def test_local_config_routes_xiaoyuzhou_before_other_rules(self):
        """The checked-in config must prioritize both domains over rulesets."""
        config = (ROOT / "blair_group.conf").read_text()
        lines = config.splitlines()
        start = lines.index("[Rule]")
        first_ruleset = next(
            i for i in range(start, len(lines)) if lines[i].startswith("RULE-SET,")
        )
        for rule in RULES:
            self.assertEqual(lines.count(rule), 1)
            self.assertTrue(start < lines.index(rule) < first_ruleset)

    def test_release_step_preserves_other_rules_and_is_repeatable(self):
        """Fresh downloads and existing conflicting rules receive one override."""
        original = (
            "[General]\nskip-proxy = 100.64.0.0/10\n"
            "[Rule]\nDOMAIN-SUFFIX,example.com,PROXY\n"
            "DOMAIN-SUFFIX,xiaoyuzhoufm.com,PROXY\n"
            "DOMAIN-SUFFIX,xyzcdn.net,DIRECT\nFINAL,PROXY\n"
            "[MITM]\nenable = false\n"
        )
        expected = original.replace(
            "DOMAIN-SUFFIX,xiaoyuzhoufm.com,PROXY\n", ""
        ).replace("DOMAIN-SUFFIX,xyzcdn.net,DIRECT\n", "")
        expected = expected.replace("[Rule]\n", "[Rule]\n" + "\n".join(RULES) + "\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release").mkdir()
            configs = [root / "release" / name for name in ("lazy.conf", "blair_group.conf")]
            for config in configs:
                config.write_text(original)
            for _ in range(2):
                result = subprocess.run(
                    ["bash", "-c", release_step()], cwd=root,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                for config in configs:
                    self.assertEqual(config.read_text(), expected)

    def test_missing_rule_section_does_not_replace_original(self):
        """An upstream format change must stop publishing, keeping the input."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release").mkdir()
            config = root / "release/lazy.conf"
            config.write_text("[General]\n# missing rules\n")
            result = subprocess.run(
                ["bash", "-c", release_step()], cwd=root,
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config.read_text(), "[General]\n# missing rules\n")

    def test_published_config_waits_for_cache_and_rejects_stale_content(self):
        """Verify the actual published URL, retry cached bytes, and fail on drift."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release").mkdir()
            expected = root / "release/blair_group.conf"
            expected.write_text("[Rule]\n" + "\n".join(RULES) + "\n")
            curl = root / "curl"
            curl.write_text(
                "#!/bin/bash\nset -eu\n"
                "for argument in \"$@\"; do last_argument=$argument; done\n"
                "test \"$last_argument\" = \"$PUBLISHED_CONFIG_URL\"\n"
                "while [[ $1 != --output ]]; do shift; done\n"
                "counter=0\n"
                "if [[ -f attempts ]]; then counter=$(cat attempts); fi\n"
                "counter=$((counter + 1))\nprintf '%s' \"$counter\" > attempts\n"
                "if [[ $counter -lt 2 || ${KEEP_STALE:-0} == 1 ]]; then\n"
                "  printf 'outdated config' > \"$2\"\n"
                "else\n  cp release/blair_group.conf \"$2\"\nfi\n"
            )
            curl.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": str(root) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
                "PUBLISHED_CONFIG_URL": "https://example.invalid/release/blair_group.conf",
                "CONFIG_SYNC_ATTEMPTS": "2",
                "CONFIG_SYNC_DELAY_SECONDS": "0",
            }
            for keep_stale in ("0", "1"):
                with self.subTest(keep_stale=keep_stale):
                    (root / "attempts").write_text("0")
                    result = subprocess.run(
                        ["bash", "-c", release_step("Verify published lazy config")],
                        cwd=root, env={**environment, "KEEP_STALE": keep_stale},
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(result.returncode, int(keep_stale), result.stderr)
                    self.assertEqual((root / "attempts").read_text(), "2")
            self.assertEqual(expected.read_text(), "[Rule]\n" + "\n".join(RULES) + "\n")


if __name__ == "__main__":
    unittest.main()
