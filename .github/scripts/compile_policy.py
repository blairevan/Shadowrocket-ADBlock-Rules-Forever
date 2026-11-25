"""Compile canonical policy/*.txt lists into Shadowrocket and Mihomo rulesets."""

from pathlib import Path
import re
import sys


DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
    re.IGNORECASE,
)

POLICY_SPECS = (
    ("ads.txt", "blair-ads.list", "mihomo-ads.list", "Unified Ad & Telemetry Blocklist"),
    ("hsbc-hk.txt", "blair-hsbc-hk.list", "mihomo-hsbc-hk.list", "Reward+ & HSBC HK"),
    ("direct-overrides.txt", "blair-direct.list", "mihomo-direct.list", "Explicit Direct Overrides"),
)


def parse_policy_lines(text: str, source_name: str) -> list[str]:
    """Validate canonical '+.domain' or 'domain' entries and reject duplicates."""
    entries: list[str] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+."):
            host = line[2:]
            canonical = "+." + host.lower()
        else:
            host = line
            canonical = host.lower()
        if not DOMAIN_RE.fullmatch(host):
            raise ValueError(f"{source_name}:{lineno}: invalid domain entry: {raw!r}")
        if canonical in seen:
            raise ValueError(f"{source_name}:{lineno}: duplicate entry: {canonical}")
        seen.add(canonical)
        entries.append(canonical)
    if not entries:
        raise ValueError(f"{source_name}: policy file contains no active entries")
    return entries


def split_matchers(entries: list[str]) -> tuple[set[str], set[str]]:
    """Separate exact host entries and suffix domain entries."""
    exact = {item for item in entries if not item.startswith("+.")}
    suffix = {item[2:] for item in entries if item.startswith("+.")}
    return exact, suffix


def matches_any(domain: str, exact: set[str], suffix: set[str]) -> bool:
    """Return True if a domain or suffix is covered by the target matcher sets."""
    host = domain[2:] if domain.startswith("+.") else domain
    if host in exact:
        return True
    parts = host.split(".")
    return any(".".join(parts[i:]) in suffix for i in range(len(parts)))


def check_no_ad_conflicts(
    ads: list[str], protected: dict[str, list[str]]
) -> None:
    """Refuse builds where ads.txt would block any protected direct/routed domain."""
    ad_exact, ad_suffix = split_matchers(ads)
    for policy_name, entries in protected.items():
        for entry in entries:
            if matches_any(entry, ad_exact, ad_suffix):
                raise ValueError(
                    f"ads.txt conflicts with protected entry {entry!r} in {policy_name}"
                )


def render_shadowrocket_domain_set(entries: list[str], title: str) -> str:
    """Render Shadowrocket DOMAIN-SET lines ('.domain' for suffix, 'domain' for exact)."""
    suffix_count = sum(1 for item in entries if item.startswith("+."))
    exact_count = len(entries) - suffix_count
    header = [
        f"# NAME: {title} (Shadowrocket DOMAIN-SET)",
        f"# GENERATED_BY: .github/scripts/compile_policy.py",
        f"# TOTAL: {len(entries)} (suffix={suffix_count}, exact={exact_count})",
    ]
    body = ["." + item[2:] if item.startswith("+.") else item for item in entries]
    return "\n".join(header + body) + "\n"


def render_mihomo_text_ruleset(entries: list[str]) -> str:
    """Render Mihomo domain text ruleset ('+.domain' for suffix, 'domain' for exact)."""
    return "\n".join(entries) + "\n"


def compile_directory(root: Path) -> dict[str, int]:
    """Validate all policy/*.txt sources and atomically emit rules/*.list outputs."""
    policy_dir = root / "policy"
    rules_dir = root / "rules"
    parsed: dict[str, list[str]] = {}
    for src_name, _, _, _ in POLICY_SPECS:
        src_path = policy_dir / src_name
        parsed[src_name] = parse_policy_lines(src_path.read_text(encoding="utf-8"), src_name)

    check_no_ad_conflicts(
        parsed["ads.txt"],
        {
            "hsbc-hk.txt": parsed["hsbc-hk.txt"],
            "direct-overrides.txt": parsed["direct-overrides.txt"],
        },
    )

    outputs: list[tuple[Path, str]] = []
    counts: dict[str, int] = {}
    for src_name, sr_name, mh_name, title in POLICY_SPECS:
        entries = parsed[src_name]
        counts[src_name] = len(entries)
        outputs.append((rules_dir / sr_name, render_shadowrocket_domain_set(entries, title)))
        outputs.append((rules_dir / mh_name, render_mihomo_text_ruleset(entries)))

    rules_dir.mkdir(parents=True, exist_ok=True)
    for path, content in outputs:
        path.write_text(content, encoding="utf-8")
    return counts


def main(arguments: list[str]) -> int:
    """Compile SSOT policy files rooted at the repository directory."""
    root = Path(arguments[0]) if arguments else Path(__file__).resolve().parents[2]
    try:
        counts = compile_directory(root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Cannot compile SSOT policy: {error}", file=sys.stderr)
        return 1
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Compiled SSOT policies: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
