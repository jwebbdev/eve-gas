"""Fetch gas prices from EVE ESI public market API."""
import time
from datetime import datetime, timezone

import requests

from ..data.loader import load_gas_types

# The Forge region (Jita)
FORGE_REGION_ID = 10000002

# Cache
_price_cache: dict[str, float] | None = None
_cache_time: float = 0
_cache_updated_at: str = ""
CACHE_TTL = 1800  # 30 minutes


def fetch_gas_prices(force_refresh: bool = False) -> tuple[dict[str, float], str]:
    """Fetch current Jita gas prices from ESI.

    Returns:
        Tuple of (prices dict {gas_id: isk_per_unit}, updated_at ISO string).
        Falls back to stale cache on error.
    """
    global _price_cache, _cache_time, _cache_updated_at

    if not force_refresh and _price_cache and (time.time() - _cache_time) < CACHE_TTL:
        return _price_cache, _cache_updated_at

    gas_types = load_gas_types()
    prices = {}

    for gas in gas_types:
        try:
            url = (
                f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/"
                f"?type_id={gas.type_id}&order_type=sell&datasource=tranquility"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            orders = resp.json()

            # Find lowest sell price in Jita (station_id 60003760)
            jita_orders = [o for o in orders if o.get("location_id") == 60003760]
            if not jita_orders:
                # Fall back to all Forge sell orders
                jita_orders = orders

            if jita_orders:
                prices[gas.id] = min(o["price"] for o in jita_orders)
            else:
                prices[gas.id] = 0.0
        except Exception:
            prices[gas.id] = 0.0

    updated_at = datetime.now(timezone.utc).isoformat()

    # Only update cache if we got at least some valid prices
    valid_prices = {k: v for k, v in prices.items() if v > 0}
    if valid_prices:
        _price_cache = prices
        _cache_time = time.time()
        _cache_updated_at = updated_at
    elif _price_cache:
        return _price_cache, _cache_updated_at

    return prices, updated_at
