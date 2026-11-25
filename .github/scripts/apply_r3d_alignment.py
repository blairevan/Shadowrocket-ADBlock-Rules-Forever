"""Align Shadowrocket lazy configs with R3D router routing, SSOT rules, and DNS policy."""

from pathlib import Path
import re
import sys


RAW_BASE = (
    "https://raw.githubusercontent.com/blairevan/"
    "Shadowrocket-ADBlock-Rules-Forever/release/rules"
)
BLAIR_DIRECT_URL = f"{RAW_BASE}/blair-direct.list"
BLAIR_ADS_URL = f"{RAW_BASE}/blair-ads.list"
BLAIR_HSBC_URL = f"{RAW_BASE}/blair-hsbc-hk.list"

SKIP_PROXY_REQUIRED = (
    "100.64.0.0/10",
    "192.168.31.1",
    "miwifi.com",
    "www.miwifi.com",
)

GENERAL_OVERRIDES = (
    ("dns-server", "https://1.1.1.1/dns-query#proxy,https://8.8.8.8/dns-query#proxy"),
    ("direct-dns-server", "223.5.5.5,119.29.29.29"),
    ("proxy-dns-server", "223.5.5.5,119.29.29.29"),
    ("fallback-dns-server", "https://1.0.0.1/dns-query#proxy"),
    ("always-real-ip", "miwifi.com,www.miwifi.com,*.ts.net"),
)

PINNED_GROUPS = (
    "QQG = select,select=0,policy-regex-filter=^US-macbookm5$",
    "HK-IPLC-3 = select,select=0,policy-regex-filter=IPLC-HK-3",
)

PRE_RULESET_RULES = (
    f"DOMAIN-SET,{BLAIR_DIRECT_URL},DIRECT",
    "IP-CIDR,192.168.31.1/32,DIRECT,no-resolve",
)

HOST_OVERRIDES = (
    "*.lan = server:system",
    "*.local = server:system",
    "miwifi.com = 192.168.31.1",
    "www.miwifi.com = 192.168.31.1",
)

GROUPS_BEGIN = "# BEGIN R3D pinned proxy groups"
GROUPS_END = "# END R3D pinned proxy groups"
PRE_BEGIN = "# BEGIN R3D pre-ruleset overrides"
PRE_END = "# END R3D pre-ruleset overrides"
POST_YT_BEGIN = "# BEGIN R3D router alignment rules"
POST_YT_END = "# END R3D router alignment rules"
HOST_BEGIN = "# BEGIN R3D host overrides"
HOST_END = "# END R3D host overrides"


def strip_managed_block(body: str, begin: str, end: str) -> str:
    """Remove an existing managed block bounded by BEGIN/END markers."""
    pattern = rf"(?m)^{re.escape(begin)}\n.*?^{re.escape(end)}\n?"
    return re.sub(pattern, "", body, flags=re.DOTALL)


def format_block(begin: str, lines: tuple[str, ...], end: str) -> str:
    """Render a newline-terminated managed block."""
    return begin + "\n" + "\n".join(lines) + "\n" + end + "\n"


def split_section(text: str, section: str) -> tuple[re.Match[str], str]:
    """Locate a single INI-style section and return its match and body."""
    pattern = re.compile(
        rf"(?ms)^(\[{re.escape(section)}\][ \t]*\n)(.*?)(?=^\[|\Z)"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one [{section}] section")
    return matches[0], matches[0][2]


def replace_section(text: str, section: str, new_body: str) -> str:
    """Replace the body of a single validated section."""
    match, _ = split_section(text, section)
    return text[:match.start()] + match[1] + new_body + text[match.end():]


def upsert_general_key(body: str, key: str, value: str) -> str:
    """Set a [General] option, uncommenting its template placeholder if present."""
    active_re = re.compile(rf"(?m)^{re.escape(key)}[ \t]*=[^\r\n]*$")
    active_matches = list(active_re.finditer(body))
    if len(active_matches) > 1:
        raise ValueError(f"multiple {key} settings in [General]")
    replacement = f"{key} = {value}"
    if active_matches:
        m = active_matches[0]
        return body[:m.start()] + replacement + body[m.end():]

    commented_re = re.compile(rf"(?m)^#[ \t]*{re.escape(key)}[ \t]*=[^\r\n]*$")
    commented_matches = list(commented_re.finditer(body))
    if commented_matches:
        m = commented_matches[0]
        return body[:m.start()] + replacement + body[m.end():]

    suffix = "" if body.endswith("\n") else "\n"
    return body + suffix + replacement + "\n"


def update_skip_proxy(body: str) -> str:
    """Ensure local router and Tailscale ranges are included in skip-proxy."""
    pattern = re.compile(r"(?m)^(skip-proxy[ \t]*=[ \t]*)([^\r\n]*)$")
    matches = list(pattern.finditer(body))
    if len(matches) > 1:
        raise ValueError("multiple skip-proxy settings in [General]")
    if not matches:
        suffix = "" if body.endswith("\n") else "\n"
        return body + suffix + "skip-proxy = " + ",".join(SKIP_PROXY_REQUIRED) + "\n"
    match = matches[0]
    items = [item.strip() for item in match[2].split(",") if item.strip()]
    for required in SKIP_PROXY_REQUIRED:
        if required not in items:
            items.append(required)
    return body[:match.start()] + match[1] + ",".join(items) + body[match.end():]


def patch_general(body: str) -> str:
    """Apply DNS and skip-proxy settings aligned with R3D."""
    body = update_skip_proxy(body)
    for key, value in GENERAL_OVERRIDES:
        body = upsert_general_key(body, key, value)
    return body


def patch_proxy_groups(body: str) -> tuple[str, bool]:
    """Pin YouTube to QQG and add HK-IPLC-3 when policy groups are present."""
    body = strip_managed_block(body, GROUPS_BEGIN, GROUPS_END)
    yt_re = re.compile(r"(?m)^YouTube[ \t]*=[ \t]*select,([^\r\n]+)$")
    matches = list(yt_re.finditer(body))
    if not matches:
        return body, False
    if len(matches) > 1:
        raise ValueError("multiple YouTube proxy groups in [Proxy Group]")

    match = matches[0]
    tokens = [token.strip() for token in match[1].split(",") if token.strip()]
    policies = [t for t in tokens if "=" not in t and t != "QQG"]
    params = [t for t in tokens if "=" in t and not t.startswith("policy-select-name=")]
    updated_yt = "YouTube = select," + ",".join(
        ["QQG", *policies, *params, "policy-select-name=QQG"]
    )
    pinned_block = format_block(GROUPS_BEGIN, PINNED_GROUPS, GROUPS_END)
    new_body = body[:match.start()] + pinned_block + updated_yt + body[match.end():]
    return new_body, True


def patch_rules(body: str, has_groups: bool) -> str:
    """Wire SSOT direct, ads, and HSBC HK DOMAIN-SET rules in exact priority order."""
    body = strip_managed_block(body, PRE_BEGIN, PRE_END)
    body = strip_managed_block(body, POST_YT_BEGIN, POST_YT_END)

    if not re.search(r"(?m)^FINAL,PROXY[ \t]*$", body):
        raise ValueError("expected FINAL,PROXY fallback rule in [Rule]")

    pre_block = format_block(PRE_BEGIN, PRE_RULESET_RULES, PRE_END)
    xyz_match = re.search(r"(?m)^DOMAIN-SUFFIX,xyzcdn\.net,DIRECT[ \t]*\n", body)
    if xyz_match:
        body = body[:xyz_match.end()] + pre_block + body[xyz_match.end():]
    else:
        first_ruleset = re.search(r"(?m)^RULE-SET,", body)
        if not first_ruleset:
            raise ValueError("expected at least one RULE-SET entry in [Rule]")
        body = body[:first_ruleset.start()] + pre_block + body[first_ruleset.start():]

    yt_rule_re = re.compile(
        r"(?m)^RULE-SET,[^\r\n]*/YouTube/YouTube\.list,[^\r\n]+\n"
    )
    yt_matches = list(yt_rule_re.finditer(body))
    if len(yt_matches) != 1:
        raise ValueError("expected exactly one YouTube RULE-SET entry in [Rule]")

    hk_policy = "HK-IPLC-3" if has_groups else "PROXY"
    post_yt_rules = (
        f"DOMAIN-SET,{BLAIR_ADS_URL},REJECT",
        f"DOMAIN-SET,{BLAIR_HSBC_URL},{hk_policy}",
    )
    post_yt_block = format_block(POST_YT_BEGIN, post_yt_rules, POST_YT_END)
    yt_match = yt_matches[0]
    return body[:yt_match.end()] + post_yt_block + body[yt_match.end():]


def patch_host(body: str) -> str:
    """Ensure local LAN and router DNS host mappings exist in [Host]."""
    body = strip_managed_block(body, HOST_BEGIN, HOST_END)
    override_keys = {line.split("=", 1)[0].strip() for line in HOST_OVERRIDES}
    cleaned_lines = [
        line for line in body.splitlines(keepends=True)
        if not ("=" in line and not line.lstrip().startswith("#")
                and line.split("=", 1)[0].strip() in override_keys)
    ]
    cleaned = "".join(cleaned_lines)
    if cleaned and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned + format_block(HOST_BEGIN, HOST_OVERRIDES, HOST_END)


def patch_config(text: str) -> str:
    """Validate sections and apply full R3D alignment idempotently."""
    _, general_body = split_section(text, "General")
    text = replace_section(text, "General", patch_general(general_body))

    _, group_body = split_section(text, "Proxy Group")
    new_group_body, has_groups = patch_proxy_groups(group_body)
    text = replace_section(text, "Proxy Group", new_group_body)

    _, rule_body = split_section(text, "Rule")
    text = replace_section(text, "Rule", patch_rules(rule_body, has_groups))

    _, host_body = split_section(text, "Host")
    text = replace_section(text, "Host", patch_host(host_body))
    return text


def main(arguments: list[str]) -> int:
    """Validate every input config before writing any changes."""
    if not arguments:
        print("usage: apply_r3d_alignment.py CONFIG [CONFIG ...]", file=sys.stderr)
        return 2
    try:
        updates = [
            (Path(name), patch_config(Path(name).read_text(encoding="utf-8")))
            for name in arguments
        ]
        for path, content in updates:
            path.write_text(content, encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Cannot apply R3D alignment: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
