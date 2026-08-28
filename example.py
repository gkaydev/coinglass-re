import asyncio
import json
import os

from coinglass import fetch_liquidation_map

result = asyncio.run(fetch_liquidation_map("BTC", obe_token=os.environ.get("COINGLASS_OBE_TOKEN")))
print(json.dumps(result, indent=2))
