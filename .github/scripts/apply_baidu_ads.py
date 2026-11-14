"""Retain narrowly scoped Netdisk ad overrides when lazy configs are refreshed."""

from pathlib import Path
import re
import sys


AD_HOSTS = (
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
    "entry-su1.ubixioe.com",
    "adx-cfg-u1.ubixioe.com",
    "adx-data-u1.ubixioe.com",
)
AD_REWRITES = (
    r"^https?://pan\.baidu\.com/buy/ad/conf(?:\?|$) - reject-200",
    r"^https?://mobads\.baidu\.com/ads/pa/8/gray/__pasys_remote_banner\.php(?:\?|$) - reject-200",
)
BEGIN = "# BEGIN Baidu Netdisk ad overrides"
END = "# END Baidu Netdisk ad overrides"


def prepend_overrides(body: str, rules: tuple[str, ...]) -> str:
    """Replace only our managed block, keeping all other settings in order."""
    pattern = rf"(?m)^{re.escape(BEGIN)}\n.*?^{re.escape(END)}\n"
    body = re.sub(pattern, "", body, flags=re.DOTALL)
    return BEGIN + "\n" + "\n".join(rules) + "\n" + END + "\n" + body


def add_mitm_hosts(body: str) -> str:
    """Append only required hosts without changing certificate or enable settings."""
    pattern = re.compile(r"(?m)^(hostname[ \t]*=[ \t]*)([^\r\n]*)$")
    matches = list(pattern.finditer(body))
    if len(matches) > 1:
        raise ValueError("multiple MITM hostname settings")
    if not matches:
        return body.rstrip("\n") + "\nhostname = pan.baidu.com, mobads.baidu.com\n"
    match = matches[0]
    hosts = [host.strip() for host in match[2].split(",") if host.strip()]
    for host in ("pan.baidu.com", "mobads.baidu.com"):
        if "-" + host in hosts:
            raise ValueError(f"required MITM host is explicitly excluded: {host}")
        if host not in hosts:
            hosts.append(host)
    return body[:match.start()] + match[1] + ", ".join(hosts) + body[match.end():]


def patch_config(text: str) -> str:
    """Validate required sections and apply host, path and MITM overrides."""
    for section in ("Rule", "URL Rewrite", "MITM"):
        pattern = re.compile(
            rf"(?ms)^(\[{re.escape(section)}\][ \t]*\n)(.*?)(?=^\[|\Z)"
        )
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one [{section}] section")
        match = matches[0]
        body = match[2]
        if section == "Rule":
            body = prepend_overrides(body, tuple(f"DOMAIN,{host},REJECT" for host in AD_HOSTS))
        elif section == "URL Rewrite":
            body = prepend_overrides(body, AD_REWRITES)
        else:
            body = add_mitm_hosts(body)
        text = text[:match.start()] + match[1] + body + text[match.end():]
    return text


def main(arguments: list[str]) -> int:
    """Validate every input before updating any generated configuration."""
    if not arguments:
        print("usage: apply_baidu_ads.py CONFIG [CONFIG ...]", file=sys.stderr)
        return 2
    try:
        updates = [(Path(name), patch_config(Path(name).read_text())) for name in arguments]
        for path, content in updates:
            path.write_text(content)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Cannot apply Netdisk ad overrides: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
