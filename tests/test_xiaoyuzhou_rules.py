"""Exercise the real release step without network access or publishing."""

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
RULES = (
    "DOMAIN-SUFFIX,xiaoyuzhoufm.com,DIRECT",
    "DOMAIN-SUFFIX,xyzcdn.net,DIRECT",
)


def release_step():
    """Read the shell block that patches freshly downloaded lazy configs."""
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    section = workflow.split(
        "      - name: Keep Xiaoyuzhou connections direct\n        run: |\n", 1
    )[1].split("\n      - name:", 1)[0]
    return textwrap.dedent(section)


class XiaoyuzhouRulesTests(unittest.TestCase):
    """Check rule priority, preservation, repeatability, and failure behavior."""

    def test_local_config_routes_xiaoyuzhou_before_other_rules(self):
        """The checked-in config must prioritize both domains over rulesets."""
        config = (ROOT / "lazy_group.conf").read_text()
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
            configs = [root / "release" / name for name in ("lazy.conf", "lazy_group.conf")]
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


if __name__ == "__main__":
    unittest.main()
