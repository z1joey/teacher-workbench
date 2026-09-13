"""阿里云 DirectMail 邮件发送（HTTP RPC + HMAC-SHA1 签名）。

DirectMail's RPC API takes all params percent-encoded and sorted, signed with
HMAC-SHA1 over "POST&/&<encoded-params>" using the secret + "&". We post
form-encoded so no SDK dependency is needed (httpx only). Failures raise
MailError; callers map it to a 502.
"""
import base64
import hashlib
import hmac
import ipaddress
import re
import secrets
import socket
import urllib.parse
from datetime import datetime, timezone

import httpx

from .settings import (
    ALI_ACCESS_KEY_ID,
    ALI_ACCESS_KEY_SECRET,
    ALI_DM_REGION,
    ALI_NO_REPLY_EMAIL,
)

TIMEOUT_SECONDS = 15
_FOLLOW_REDIRECTS = False  # POST 到固定 https 端点，禁止重定向

# 防 SSRF：region 只允许合法字符集，域名固定为 *.aliyuncs.com，https only
_REGION_RE = re.compile(r"^[a-z0-9-]{2,20}$")
# 私网/环回/链路本地/保留地址一律拒绝（云元数据 100.100.100.200 也在此列）


class MailError(Exception):
    """DirectMail 调用失败（网络/签名/业务错误），由路由层转成 502。"""


def _endpoint(region: str) -> str:
    # DirectMail 的接入点是固定的 dm.aliyuncs.com，区域由 RegionId 参数控制。
    # host 是硬编码常量 + 公网 IP 校验，杜绝 SSRF。
    if not _REGION_RE.fullmatch(region):
        raise MailError(f"非法的 DirectMail region: {region!r}")
    host = "dm.aliyuncs.com"
    _assert_public_host(host)
    return f"https://{host}/"


def _assert_public_host(host: str) -> None:
    """解析主机名并确认全部 IP 都是公网地址（防内网/云元数据 SSRF）。"""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise MailError(f"DirectMail 域名解析失败: {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise MailError(f"DirectMail 域名解析到非公网地址: {ip}")


def _percent_encode(value: str) -> str:
    # 阿里云 RPC 规范：RFC3986 编码（保留字集比 urlencode 小）
    return urllib.parse.quote(value, safe="-_.~")


def _sign(params: dict, access_key_secret: str) -> str:
    canonical = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(params.items())
    )
    string_to_sign = f"POST&{_percent_encode('/')}&{_percent_encode(canonical)}"
    digest = hmac.new(
        (access_key_secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def send_html_mail(to: str, subject: str, html: str) -> None:
    """Send one HTML mail from the verified DirectMail account. Raises
    MailError on any failure."""
    if not (ALI_ACCESS_KEY_ID and ALI_ACCESS_KEY_SECRET and ALI_NO_REPLY_EMAIL):
        raise MailError("未配置 DirectMail 发信凭据")
    params = {
        "AccessKeyId": ALI_ACCESS_KEY_ID,
        "Action": "SingleSendMail",
        "AccountName": ALI_NO_REPLY_EMAIL,
        "AddressType": "1",
        "Format": "JSON",
        "FromAlias": "教师工作台",
        "HtmlBody": html,
        "RegionId": ALI_DM_REGION,
        "ReplyToAddress": "false",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": secrets.token_hex(16),
        "SignatureVersion": "1.0",
        "Subject": subject,
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ToAddress": to,
        "Version": "2015-11-23",
    }
    params["Signature"] = _sign(params, ALI_ACCESS_KEY_SECRET)
    try:
        resp = httpx.post(
            _endpoint(ALI_DM_REGION),
            data=params,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=_FOLLOW_REDIRECTS,
        )
    except httpx.HTTPError as e:
        raise MailError(f"连接 DirectMail 失败: {e}") from e
    if resp.status_code != 200:
        raise MailError(f"DirectMail 返回 {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    if "Code" in body:
        # HTTP 200 也可能带业务错误码（如 InvalidSendMail.DNS）
        raise MailError(f"DirectMail 错误 {body.get('Code')}: {body.get('Message', '')}")
