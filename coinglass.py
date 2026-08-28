import asyncio
import base64
import gzip
import json
import time
import zlib

import httpx
from Crypto.Cipher import AES

_V_RAW_KEYS: dict[str, str] = {
    "55": "170b070da9654622",
    "66": "d6537d845a964081",
    "77": "863f08689c97435b",
}

_BASE_URL = "https://capi.coinglass.com/api/index/2/exLiqMap"


def _aes_ecb_decrypt_bytes(b64_ciphertext: str, key: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(base64.b64decode(b64_ciphertext))


def _derive_outer_key(v_hdr: str, time_hdr: str) -> bytes:
    if v_hdr in _V_RAW_KEYS:
        # raw key is latin-1 encoded bytes re-expressed as base64, then truncated
        raw = _V_RAW_KEYS[v_hdr]
        return base64.b64encode(raw.encode("latin-1")).decode()[:16].encode("utf-8")
    # fallback: server time header acts as the key seed
    return base64.b64encode(time_hdr.encode()).decode()[:16].encode()


def _decrypt_inner_key(encrypted_user_hdr: str, outer_key: bytes) -> bytes:
    raw = _aes_ecb_decrypt_bytes(encrypted_user_hdr, outer_key)
    raw = raw[: -raw[-1]]  # strip PKCS7 padding
    decompressed = gzip.decompress(raw).decode()
    return decompressed.strip('"').encode()


async def fetch_liquidation_map(
    symbol: str,
    *,
    interval: str = "1",
    limit: str = "1500",
    obe_token: str | None = None,
) -> dict:
    cache_ts_ms = str(int(time.time() * 1000))

    headers = {
        "cache-ts-v2": cache_ts_ms,
        "encryption": "true",
        "language": "en",
        "origin": "https://www.coinglass.com",
        "referer": "https://www.coinglass.com/",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    if obe_token:
        headers["obe"] = obe_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _BASE_URL,
            params={"merge": "true", "symbol": symbol, "interval": interval, "limit": limit},
            headers=headers,
        )

    body = resp.json()
    if body.get("success") is False:
        if body.get("code") == "40000":
            raise RuntimeError(
                "coinglass rejected the request (not logged in) — the liquidation "
                "map endpoints now require an authenticated session. Pass your "
                "browser's 'obe' cookie value as obe_token= to fetch_liquidation_map()."
            )
        raise RuntimeError(f"coinglass rejected the request: {body}")

    resp_headers = resp.headers
    v_hdr = resp_headers.get("v", "")
    time_hdr = resp_headers.get("time", "")
    encrypted_user_hdr = resp_headers.get("user", "")
    if not encrypted_user_hdr:
        raise RuntimeError("coinglass response carried no 'user' header to derive the inner key from")

    outer_key = _derive_outer_key(v_hdr, time_hdr)
    inner_key = _decrypt_inner_key(encrypted_user_hdr, outer_key)

    encrypted_payload = body["data"]

    raw = _aes_ecb_decrypt_bytes(encrypted_payload, inner_key)
    raw = raw[: -raw[-1]]  # strip PKCS7 padding
    try:
        decrypted_json = gzip.decompress(raw)
    except gzip.BadGzipFile:
        try:
            # body may use raw deflate (no gzip wrapper) - \x02 first byte is a valid deflate block header
            decrypted_json = zlib.decompress(raw, -15)
        except Exception:
            raise RuntimeError(
                f"decompression failed — inner key may be wrong (v={v_hdr!r})"
            )

    return json.loads(decrypted_json)
