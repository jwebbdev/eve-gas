"""Load gas harvesting data from YAML files."""
from pathlib import Path

import yaml

from ..models import (
    BurstCharge,
    BurstModule,
    GasSite,
    GasType,
    HarvesterModule,
    ShipDef,
    ShipRole,
)

DATA_DIR = Path(__file__).parent


def load_gas_types() -> list[GasType]:
    """Load all gas type definitions from YAML."""
    path = DATA_DIR / "gas_types.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        GasType(
            id=g["id"],
            name=g["name"],
            type_id=g["type_id"],
            category=g["category"],
            volume=g["volume"],
        )
        for g in data["gas_types"]
    ]


def load_ships() -> dict[str, ShipDef]:
    """Load all ship definitions from YAML. Returns dict keyed by ship id."""
    path = DATA_DIR / "ships.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ships = {}
    for s in data["ships"]:
        ship = ShipDef(
            id=s["id"],
            name=s["name"],
            role=ShipRole(s["role"]),
            turret_slots=s.get("turret_slots", 0),
            high_slots=s.get("high_slots", 0),
            module_type=s.get("module_type", "scoop"),
            ore_hold_m3=s.get("ore_hold_m3", 0),
            cargo_m3=s.get("cargo_m3", 0),
            role_yield_bonus=s.get("role_yield_bonus", 0),
            yield_bonus_per_level=s.get("yield_bonus_per_level", 0),
            yield_bonus_skill=s.get("yield_bonus_skill", ""),
            role_cycle_time_bonus=s.get("role_cycle_time_bonus", 0),
            cycle_time_bonus_per_level=s.get("cycle_time_bonus_per_level", 0),
            cycle_time_bonus_skill=s.get("cycle_time_bonus_skill", ""),
            can_boost=s.get("can_boost", False),
            burst_slots=s.get("burst_slots", 0),
            burst_strength_per_level=s.get("burst_strength_per_level", 0),
            burst_strength_skill=s.get("burst_strength_skill", ""),
            can_covert_cloak=s.get("can_covert_cloak", False),
            notes=s.get("notes", ""),
        )
        ships[ship.id] = ship
    return ships


def load_scoops() -> list[HarvesterModule]:
    """Load gas cloud scoop definitions (for frigates/destroyers)."""
    path = DATA_DIR / "modules.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        HarvesterModule(
            id=m["id"],
            name=m["name"],
            yield_per_cycle=m["yield_per_cycle"],
            cycle_time=m["cycle_time"],
            meta_level=m.get("meta_level", 0),
            residue_probability=m.get("residue_probability", 0),
            residue_multiplier=m.get("residue_multiplier", 0),
        )
        for m in data["scoops"]
    ]


def load_harvesters() -> list[HarvesterModule]:
    """Load gas cloud harvester definitions (for barges/exhumers)."""
    path = DATA_DIR / "modules.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        HarvesterModule(
            id=m["id"],
            name=m["name"],
            yield_per_cycle=m["yield_per_cycle"],
            cycle_time=m["cycle_time"],
            meta_level=m.get("meta_level", 0),
            residue_probability=m.get("residue_probability", 0),
            residue_multiplier=m.get("residue_multiplier", 0),
        )
        for m in data["harvesters"]
    ]


def load_all_modules() -> dict[str, list[HarvesterModule]]:
    """Load all gas modules, keyed by type ('scoop' and 'harvester')."""
    return {
        "scoop": load_scoops(),
        "harvester": load_harvesters(),
    }


def load_burst_charges() -> list[BurstCharge]:
    """Load burst charge definitions from YAML."""
    path = DATA_DIR / "modules.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        BurstCharge(
            id=c["id"],
            name=c["name"],
            effect=c["effect"],
            base_bonus=c.get("base_bonus", 0),
        )
        for c in data.get("burst_charges", [])
    ]


def load_sites() -> list[GasSite]:
    """Load all gas site definitions from YAML."""
    path = DATA_DIR / "sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        GasSite(
            id=s["id"],
            name=s["name"],
            region=s.get("region", ""),
            wh_classes=s.get("wh_classes", ""),
            gas_clouds=s["gas_clouds"],
            npc_spawn_seconds=s.get("npc_spawn_seconds"),
        )
        for s in data["sites"]
    ]
