"""Fetch gas prices from EVE ESI public market API."""
import time
from datetime import datetime, timezone

import requests

from ..data.loader import load_gas_types

# The Forge region (Jita)
FORGE_REGION_ID = 10000002
JITA_STATION_ID = 60003760

# Cache
_price_cache: dict | None = None
_cache_time: float = 0
_cache_updated_at: str = ""
CACHE_TTL = 1800  # 30 minutes


def fetch_gas_prices(force_refresh: bool = False) -> tuple[dict, str]:
    """Fetch current Jita gas prices (both buy and sell) from ESI.

    Returns:
        Tuple of (prices dict, updated_at ISO string).
        Prices dict: {gas_id: {"buy": float, "sell": float}}
        Falls back to stale cache on error.
    """
    global _price_cache, _cache_time, _cache_updated_at

    if not force_refresh and _price_cache and (time.time() - _cache_time) < CACHE_TTL:
        return _price_cache, _cache_updated_at

    gas_types = load_gas_types()
    prices = {}

    for gas in gas_types:
        buy_price = 0.0
        sell_price = 0.0

        # Fetch sell orders (lowest = what a buyer pays)
        try:
            url = (
                f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/"
                f"?type_id={gas.type_id}&order_type=sell&datasource=tranquility"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            orders = resp.json()
            jita_orders = [o for o in orders if o.get("location_id") == JITA_STATION_ID]
            if not jita_orders:
                jita_orders = orders
            if jita_orders:
                sell_price = min(o["price"] for o in jita_orders)
        except Exception:
            pass

        # Fetch buy orders (highest = what a seller gets instantly)
        try:
            url = (
                f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/"
                f"?type_id={gas.type_id}&order_type=buy&datasource=tranquility"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            orders = resp.json()
            jita_orders = [o for o in orders if o.get("location_id") == JITA_STATION_ID]
            if not jita_orders:
                jita_orders = orders
            if jita_orders:
                buy_price = max(o["price"] for o in jita_orders)
        except Exception:
            pass

        prices[gas.id] = {"buy": buy_price, "sell": sell_price}

    updated_at = datetime.now(timezone.utc).isoformat()

    valid = any(p["buy"] > 0 or p["sell"] > 0 for p in prices.values())
    if valid:
        _price_cache = prices
        _cache_time = time.time()
        _cache_updated_at = updated_at
    elif _price_cache:
        return _price_cache, _cache_updated_at

    return prices, updated_at
