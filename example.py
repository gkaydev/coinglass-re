import asyncio
import json

from coinglass import fetch_liquidation_map

result = asyncio.run(fetch_liquidation_map("BTC"))
print(json.dumps(result, indent=2))
