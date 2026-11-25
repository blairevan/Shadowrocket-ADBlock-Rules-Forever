"""Verify SSOT policy compilation, R3D alignment overrides, and workflow wiring."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILE_SCRIPT = ROOT / ".github/scripts/compile_policy.py"
ALIGN_SCRIPT = ROOT / ".github/scripts/apply_r3d_alignment.py"
BAIDU_SCRIPT = ROOT / ".github/scripts/apply_baidu_ads.py"

RAW_BASE = (
    "https://raw.githubusercontent.com/blairevan/"
    "Shadowrocket-ADBlock-Rules-Forever/release/rules"
)
BLAIR_DIRECT_URL = f"{RAW_BASE}/blair-direct.list"
BLAIR_ADS_URL = f"{RAW_BASE}/blair-ads.list"
BLAIR_HSBC_URL = f"{RAW_BASE}/blair-hsbc-hk.list"

GROUP_BASE = """[General]
skip-proxy = 100.64.0.0/10,192.168.0.0/16,localhost
dns-server = https://doh.pub/dns-query,223.5.5.5
direct-dns-server = 
fallback-dns-server = system
# always-real-ip =
# proxy-dns-server =

[Proxy Group]
AI = select,PROXY,美国节点,policy-select-name=PROXY
YouTube = select,PROXY,香港节点,美国节点,policy-select-name=PROXY
香港节点 = url-test,url=http://www.gstatic.com/generate_204,interval=600,tolerance=0,timeout=5,select=0,policy-regex-filter=HK

[Rule]
DOMAIN-SUFFIX,xiaoyuzhoufm.com,DIRECT
DOMAIN-SUFFIX,xyzcdn.net,DIRECT
RULE-SET,https://raw.githubusercontent.com/iab0x00/ProxyRules/main/Rule/AI.txt,AI
RULE-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/YouTube/YouTube.list,YouTube
DOMAIN-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Global/Global_Domain.list,PROXY
DOMAIN-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/China/China_Domain.list,DIRECT
FINAL,PROXY

[Host]
*.apple.com = server:system
localhost = 127.0.0.1
"""

SIMPLE_BASE = """[General]
skip-proxy = 100.64.0.0/10,192.168.0.0/16,localhost
dns-server = https://doh.pub/dns-query,223.5.5.5
direct-dns-server = 
fallback-dns-server = system
# always-real-ip =
# proxy-dns-server =

[Proxy Group]
# none

[Rule]
DOMAIN-SUFFIX,xiaoyuzhoufm.com,DIRECT
DOMAIN-SUFFIX,xyzcdn.net,DIRECT
RULE-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/YouTube/YouTube.list,PROXY
DOMAIN-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Global/Global_Domain.list,PROXY
FINAL,PROXY

[Host]
localhost = 127.0.0.1
"""


def run_patcher(text: str, filename: str = "blair_group.conf") -> str:
    """Apply apply_r3d_alignment.py to an isolated config file."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / filename
        path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            ["python3", "-B", str(ALIGN_SCRIPT), str(path)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return path.read_text(encoding="utf-8")


def non_comment_lines(path: Path) -> list[str]:
    """Return active non-empty, non-comment lines from a rule file."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class SSOTPolicyAndAlignmentTests(unittest.TestCase):
    """Test SSOT compilation and R3D alignment for both Shadowrocket and Mihomo."""

    def test_compile_policy_generates_exact_dual_target_outputs(self):
        """Compiled Shadowrocket and Mihomo files must stay in 1:1 parity with policy/*.txt."""
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "policy").mkdir()
            (tmp / "policy/ads.txt").write_text("# comment\n+.ads.example.com\nexact.ad.test\n")
            (tmp / "policy/hsbc-hk.txt").write_text("www.hsbc.com.hk\n")
            (tmp / "policy/direct-overrides.txt").write_text("+.argotunnel.com\nmiwifi.com\n")

            res = subprocess.run(
                ["python3", "-B", str(COMPILE_SCRIPT), str(tmp)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(
                non_comment_lines(tmp / "rules/blair-ads.list"),
                [".ads.example.com", "exact.ad.test"],
            )
            self.assertEqual(
                non_comment_lines(tmp / "rules/mihomo-ads.list"),
                ["+.ads.example.com", "exact.ad.test"],
            )
            self.assertEqual(
                non_comment_lines(tmp / "rules/blair-direct.list"),
                [".argotunnel.com", "miwifi.com"],
            )
            self.assertEqual(
                non_comment_lines(tmp / "rules/mihomo-direct.list"),
                ["+.argotunnel.com", "miwifi.com"],
            )

    def test_compile_policy_rejects_ad_conflict_with_protected_domains(self):
        """Refuse compiling if ads.txt accidentally blocks an HSBC or direct domain."""
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "policy").mkdir()
            (tmp / "policy/ads.txt").write_text("+.hsbc.com.hk\n")
            (tmp / "policy/hsbc-hk.txt").write_text("www.hsbc.com.hk\n")
            (tmp / "policy/direct-overrides.txt").write_text("+.argotunnel.com\n")

            res = subprocess.run(
                ["python3", "-B", str(COMPILE_SCRIPT), str(tmp)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("conflicts with protected entry", res.stderr)

    def test_checked_in_ssot_outputs_match_fresh_compilation(self):
        """Checked-in rules/*.list must exactly match compiled policy/*.txt."""
        domain_re = re.compile(
            r"^(?:\+\.|\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
            re.I,
        )
        pairs = (
            ("ads.txt", "blair-ads.list", "mihomo-ads.list"),
            ("hsbc-hk.txt", "blair-hsbc-hk.list", "mihomo-hsbc-hk.list"),
            ("direct-overrides.txt", "blair-direct.list", "mihomo-direct.list"),
        )
        for src_name, sr_name, mh_name in pairs:
            src_lines = non_comment_lines(ROOT / "policy" / src_name)
            sr_lines = non_comment_lines(ROOT / "rules" / sr_name)
            mh_lines = non_comment_lines(ROOT / "rules" / mh_name)
            self.assertEqual(mh_lines, src_lines)
            self.assertEqual(
                sr_lines,
                ["." + x[2:] if x.startswith("+.") else x for x in src_lines],
            )
            for item in sr_lines:
                self.assertFalse(item.startswith("+."))
                self.assertRegex(item, domain_re)

        ads = set(non_comment_lines(ROOT / "rules/mihomo-ads.list"))
        for must_block in (
            "ad.caiyunapp.com",
            "+.pos.baidu.com",
            "ad.doubleclick.net",
            "adblock.telemetry.eyeo.com",
            "ping.getadblock.com",
            "notification.adblockplus.org",
            "resource-m-r.ad-scope.com.cn",
        ):
            self.assertIn(must_block, ads)
        self.assertEqual(len(non_comment_lines(ROOT / "rules/mihomo-hsbc-hk.list")), 10)
        self.assertIn("+.argotunnel.com", non_comment_lines(ROOT / "rules/mihomo-direct.list"))

    def test_group_config_alignment_order_and_idempotency(self):
        """Grouped config pins YouTube/HK-IPLC-3, wires SSOT DOMAIN-SETs, keeps FINAL,PROXY."""
        once = run_patcher(GROUP_BASE)
        self.assertEqual(run_patcher(once), once)

        self.assertIn(
            "dns-server = https://1.1.1.1/dns-query#proxy,https://8.8.8.8/dns-query#proxy",
            once,
        )
        self.assertIn("direct-dns-server = 223.5.5.5,119.29.29.29", once)
        self.assertIn("proxy-dns-server = 223.5.5.5,119.29.29.29", once)
        self.assertIn("fallback-dns-server = https://1.0.0.1/dns-query#proxy", once)
        self.assertIn("always-real-ip = miwifi.com,www.miwifi.com,*.ts.net", once)
        self.assertIn("QQG = select,select=0,policy-regex-filter=^US-macbookm5$", once)
        self.assertIn("HK-IPLC-3 = select,select=0,policy-regex-filter=IPLC-HK-3", once)
        self.assertIn(
            "YouTube = select,QQG,PROXY,香港节点,美国节点,policy-select-name=QQG",
            once,
        )

        direct_rule = f"DOMAIN-SET,{BLAIR_DIRECT_URL},DIRECT"
        ads_rule = f"DOMAIN-SET,{BLAIR_ADS_URL},REJECT"
        hsbc_rule = f"DOMAIN-SET,{BLAIR_HSBC_URL},HK-IPLC-3"

        self.assertLess(once.index("DOMAIN-SUFFIX,xyzcdn.net,DIRECT"), once.index(direct_rule))
        self.assertLess(once.index(direct_rule), once.index("/YouTube/YouTube.list,YouTube"))
        self.assertLess(once.index("/YouTube/YouTube.list,YouTube"), once.index(ads_rule))
        self.assertLess(once.index(ads_rule), once.index(hsbc_rule))
        self.assertLess(once.index(hsbc_rule), once.index("/Global/Global_Domain.list,PROXY"))
        self.assertIn("FINAL,PROXY", once)

    def test_simple_config_uses_proxy_without_adding_policy_groups(self):
        """Non-group lazy.conf wires SSOT DOMAIN-SETs using PROXY for HSBC HK."""
        once = run_patcher(SIMPLE_BASE, filename="lazy.conf")
        self.assertEqual(run_patcher(once, filename="lazy.conf"), once)
        self.assertNotIn("QQG = select", once)
        self.assertIn(f"DOMAIN-SET,{BLAIR_DIRECT_URL},DIRECT", once)
        self.assertIn(f"DOMAIN-SET,{BLAIR_ADS_URL},REJECT", once)
        self.assertIn(f"DOMAIN-SET,{BLAIR_HSBC_URL},PROXY", once)
        self.assertIn("FINAL,PROXY", once)

    def test_checked_in_configs_and_release_workflow_include_alignment(self):
        """Checked-in configs and workflow must reflect SSOT compilation and alignment."""
        self.assertFalse((ROOT / "lazy_group.conf").exists())
        blair_text = (ROOT / "blair_group.conf").read_text(encoding="utf-8")
        self.assertIn(
            "update-url = https://raw.githubusercontent.com/blairevan/"
            "Shadowrocket-ADBlock-Rules-Forever/release/blair_group.conf",
            blair_text,
        )
        for name in ("lazy.conf", "blair_group.conf"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(run_patcher(text, filename=name), text)
            with tempfile.TemporaryDirectory() as directory:
                copy = Path(directory) / name
                copy.write_text(text, encoding="utf-8")
                res = subprocess.run(
                    ["python3", "-B", str(BAIDU_SCRIPT), str(copy)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual(copy.read_text(encoding="utf-8"), text)

        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        compile_cmd = "python3 release/.github/scripts/compile_policy.py release"
        align_cmd = "python3 release/.github/scripts/apply_r3d_alignment.py release/lazy.conf release/blair_group.conf"
        self.assertIn(compile_cmd, workflow)
        self.assertIn(align_cmd, workflow)
        self.assertLess(workflow.index("Keep Baidu Netdisk ad overrides"), workflow.index(compile_cmd))
        self.assertLess(workflow.index(compile_cmd), workflow.index(align_cmd))
        self.assertLess(workflow.index(align_cmd), workflow.index("Validate Xiaoyuzhou rules"))


if __name__ == "__main__":
    unittest.main()
