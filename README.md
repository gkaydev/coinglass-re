# coinglass-re

Reverse engineering of the two-layer AES-ECB + gzip encryption scheme used by Coinglass's internal API. This repo documents the scheme and provides a working implementation against the liquidation map endpoint.

**Status:** the crypto scheme below is still exactly how Coinglass encrypts responses today — verified live against `capi.coinglass.com/api/futures/liquidation/maxOrder`, full round trip. What's changed since this was written is that the liquidation map endpoints (`/api/index/2/exLiqMap` and its newer sibling `/api/index/5/liqMap`) now sit behind a login wall: anonymous requests get `{"code":"40000","msg":"40000","success":false}`, which is the same generic "not logged in" code Coinglass's own `userapi/info` endpoint spells out in plain English. I confirmed this by watching coinglass.com's own frontend, logged out, get rejected by the exact same call. The static guest `obe` token this repo used to ship with is dead — current anonymous page loads don't send an `obe` header at all, so there's nothing to hardcode any more. See [`Usage`](#usage) for how to supply your own logged-in session instead.

## How it works

Every response from Coinglass's internal API (`capi.coinglass.com`) carries an encrypted payload in the `data` field of the JSON body, plus three relevant response headers: `v`, `time`, and `user`. Decryption requires two passes of AES-ECB followed by gzip decompression.

The first step is deriving the outer key. If the `v` response header matches one of the hardcoded version strings extracted from their JS bundle (`"55"`, `"66"`, `"77"`), the corresponding raw key value is base64-encoded and the first 16 characters of that base64 string are used as the AES key. The `v` header is how Coinglass rotates keys server-side without redeploying clients — the JS bundle carries all known versions. If `v` is absent or unrecognised, the fallback is the `time` response header: base64-encode it, take the first 16 characters, use that as the key. The fallback exists for backwards compatibility but in practice the versioned path is always taken.

With the outer key in hand, the `user` response header (a base64-encoded AES-ECB ciphertext) is decrypted and the resulting bytes are gzip-decompressed. This yields the inner key as a JSON-quoted string, e.g. `"a3f9..."` — the surrounding quotes are stripped to get the raw key bytes.

The actual payload decryption follows the same pattern: base64-decode `data`, AES-ECB-decrypt with the inner key, gzip-decompress, JSON-parse. The result is the plaintext API response.

## Endpoint

```
GET https://capi.coinglass.com/api/index/2/exLiqMap
```

Query parameters: `merge=true`, `symbol=<SYMBOL>`, `interval=1`, `limit=1500` (these match what the live site currently sends from `/pro/futures/LiquidationMap`; older captures show `interval=5`/`limit=2000`, so the value itself isn't load-bearing — pick whatever window you want).

Required headers:

| Header | Value | Purpose |
|---|---|---|
| `cache-ts-v2` | Current Unix timestamp in milliseconds | Request freshness check — requests with a stale timestamp are rejected |
| `encryption` | `"true"` | Signals that the client expects an encrypted response |
| `obe` | *(your logged-in session's `obe` cookie value)* | Auth token. Required for this endpoint specifically — see `Status` above. Omitted entirely for endpoints that don't need login. |
| `language` | `"en"` | Localisation hint |
| `origin` / `referer` | `https://www.coinglass.com` | Standard browser headers; omitting them triggers CORS rejection |

## Usage

Install dependencies:

```
pip install httpx pycryptodome
```

Run the example:

```
python example.py
```

Without a session this fails with a clear `RuntimeError` explaining that the endpoint needs login, rather than silently returning garbage. To actually fetch and decrypt the BTC liquidation map, log in to coinglass.com in a browser, copy the value of the `obe` cookie from devtools, and either export it or pass it directly:

```
COINGLASS_OBE_TOKEN=<your obe cookie value> python example.py
```

or in code:

```python
result = await fetch_liquidation_map("BTC", obe_token="<your obe cookie value>")
```

Expect a large object containing liquidation levels aggregated across exchanges.

## Dependencies

- [`httpx`](https://www.python-httpx.org/) — async HTTP client
- [`pycryptodome`](https://pycryptodome.readthedocs.io/) — AES-ECB implementation (`Crypto.Cipher.AES`)

## Disclaimer

This project is for educational and security research purposes only. It documents an encryption scheme observed in publicly accessible network traffic from a browser session. It is not affiliated with or endorsed by Coinglass. Use responsibly and in accordance with applicable terms of service and laws.
