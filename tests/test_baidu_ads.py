"""Verify ad blocking, release integration, and preservation of user settings."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/apply_baidu_ads.py"
DOMAINS = (
    "resource-m-r.ad-scope.com.cn",
    "ad-api.adn-plus.com.cn",
    "sdk.beizi.biz",
    "sdk.zhangyuyidong.cn",
    "bj-td-menta-01-callback.advlion.com",
    "v3.gdt.qq.com",
    "v2mi.gdt.qq.com",
    "win.gdt.qq.com",
    "pgdt.ugdtimg.com",
    "api-access.pangolin-sdk-toutiao.com",
    "api-access.pangolin-sdk-toutiao1.com",
    "api-access.pangolin-sdk-toutiao-b.com",
    "entry-su1.ubixioe.com",
    "adx-cfg-u1.ubixioe.com",
    "adx-data-u1.ubixioe.com",
)
BASE = (
    "[General]\nkeep-setting = true\n[Rule]\n"
    "DOMAIN-SUFFIX,baidu.com,DIRECT\nDOMAIN-SUFFIX,cn,DIRECT\nFINAL,PROXY\n"
    "[URL Rewrite]\n^https://example.com/old https://example.com/new 302\n"
    "[MITM]\nenable = true\nhostname = *.google.cn\n"
    "# Preserve the locally configured certificate and its settings.\n"
)


def patched_config(text):
    """Apply the release script to one isolated config and return its bytes."""
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "blair_group.conf"
        config.write_text(text)
        result = subprocess.run(
            ["python3", str(SCRIPT), str(config)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return config.read_text()


class BaiduAdsTests(unittest.TestCase):
    """Exercise real config output rather than a second copy of the patcher."""

    def test_blocked_hosts_precede_broad_direct_rules(self):
        """Observed SDK hosts must be rejected before domestic direct fallbacks."""
        config = patched_config(BASE)
        for domain in DOMAINS:
            rule = f"DOMAIN,{domain},REJECT"
            self.assertEqual(config.splitlines().count(rule), 1)
            self.assertLess(config.index(rule), config.index("DOMAIN-SUFFIX,cn,DIRECT"))
        self.assertIn("DOMAIN-SUFFIX,baidu.com,DIRECT", config)
        self.assertIn("FINAL,PROXY", config)

    def test_rewrites_match_ads_without_matching_normal_netdisk_requests(self):
        """Limit rejection to the two observed ad paths, including query strings."""
        config = patched_config(BASE)
        section = config.split("[URL Rewrite]\n", 1)[1].split("[MITM]", 1)[0]
        patterns = [
            line.split()[0] for line in section.splitlines()
            if line and not line.startswith("#") and line.endswith(" - reject-200")
        ]
        for url in (
            "https://pan.baidu.com/buy/ad/conf",
            "https://pan.baidu.com/buy/ad/conf?app_id=250528",
            "https://mobads.baidu.com/ads/pa/8/gray/__pasys_remote_banner.php?test=1",
        ):
            self.assertTrue(any(re.search(pattern, url) for pattern in patterns), url)
        for url in (
            "https://pan.baidu.com/api/list?dir=/",
            "https://pan.baidu.com/rest/2.0/pcs/file?method=download",
            "https://pan.baidu.com/buy/ad/configuration",
            "https://pan.baidu.com.evil.example/buy/ad/conf",
        ):
            self.assertFalse(any(re.search(pattern, url) for pattern in patterns), url)

    def test_preserves_mitm_settings_and_is_repeatable(self):
        """Applying updates twice must preserve certificates, settings and hostname order."""
        original = BASE.replace("hostname = *.google.cn", "hostname = *.google.cn, pan.baidu.com")
        once = patched_config(original)
        self.assertEqual(patched_config(once), once)
        self.assertIn("hostname = *.google.cn, pan.baidu.com, mobads.baidu.com", once)
        self.assertIn("enable = true", once)
        self.assertIn("# Preserve the locally configured certificate and its settings.", once)
        self.assertIn("^https://example.com/old https://example.com/new 302", once)

    def test_invalid_second_config_leaves_both_originals_intact(self):
        """Validate all upstream inputs before writing any updated config."""
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("lazy.conf", "blair_group.conf")]
            originals = [BASE, "[General]\n# missing rules\n"]
            for path, original in zip(paths, originals):
                path.write_text(original)
            result = subprocess.run(
                ["python3", str(SCRIPT), *map(str, paths)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([path.read_text() for path in paths], originals)

    def test_checked_in_configs_and_release_step_include_the_patch(self):
        """Both published variants must retain the patch after an upstream refresh."""
        for name in ("lazy.conf", "blair_group.conf"):
            config = (ROOT / name).read_text()
            self.assertEqual(patched_config(config), config)
            for domain in DOMAINS:
                self.assertIn(f"DOMAIN,{domain},REJECT", config)
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        command = "python3 release/.github/scripts/apply_baidu_ads.py release/lazy.conf release/blair_group.conf"
        self.assertIn(command, workflow)
        self.assertLess(workflow.index("Keep Xiaoyuzhou connections direct"), workflow.index(command))
        self.assertLess(workflow.index(command), workflow.index("Validate Xiaoyuzhou rules"))


if __name__ == "__main__":
    unittest.main()
