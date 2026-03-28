# coinglass-re

Reverse engineering of the two-layer AES-ECB + gzip encryption scheme used by Coinglass's internal API. This repo documents the scheme and provides a working implementation against the liquidation map endpoint.

## How it works

Every response from Coinglass's internal API (`capi.coinglass.com`) carries an encrypted payload in `data.data` and three relevant response headers: `v`, `time`, and `user`. Decryption requires two passes of AES-ECB followed by gzip decompression.

The first step is deriving the outer key. If the `v` response header matches one of the hardcoded version strings extracted from their JS bundle (`"55"`, `"66"`, `"77"`), the corresponding raw key value is base64-encoded and the first 16 characters of that base64 string are used as the AES key. The `v` header is how Coinglass rotates keys server-side without redeploying clients — the JS bundle carries all known versions. If `v` is absent or unrecognised, the fallback is the `time` response header: base64-encode it, take the first 16 characters, use that as the key. The fallback exists for backwards compatibility but in practice the versioned path is always taken.

With the outer key in hand, the `user` response header (a base64-encoded AES-ECB ciphertext) is decrypted and the resulting bytes are gzip-decompressed. This yields the inner key as a JSON-quoted string, e.g. `"a3f9..."` — the surrounding quotes are stripped to get the raw key bytes.

The actual payload decryption follows the same pattern: base64-decode `data.data`, AES-ECB-decrypt with the inner key, gzip-decompress, JSON-parse. The result is the plaintext API response.

## Endpoint

```
GET https://capi.coinglass.com/api/index/2/exLiqMap
```

Query parameters: `merge=true`, `symbol=<SYMBOL>`, `interval=5`, `limit=2000`

Required headers:

| Header | Value | Purpose |
|---|---|---|
| `cache-ts-v2` | Current Unix timestamp in milliseconds | Request freshness check — requests with a stale timestamp are rejected |
| `encryption` | `"true"` | Signals that the client expects an encrypted response |
| `obe` | `s_463bd7363fdd4662b7400bcb13aefb54` | Static auth token embedded in their JS bundle |
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

This fetches and decrypts the BTC liquidation map and prints the raw JSON to stdout. Expect a large object containing liquidation levels aggregated across exchanges.

## Dependencies

- [`httpx`](https://www.python-httpx.org/) — async HTTP client
- [`pycryptodome`](https://pycryptodome.readthedocs.io/) — AES-ECB implementation (`Crypto.Cipher.AES`)

## Disclaimer

This project is for educational and security research purposes only. It documents an encryption scheme observed in publicly accessible network traffic from a browser session. It is not affiliated with or endorsed by Coinglass. Use responsibly and in accordance with applicable terms of service and laws.
