"""Data models for fleet-based gas harvesting calculations."""
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Gas types and sites
# ---------------------------------------------------------------------------

@dataclass
class GasType:
    """A harvestable gas cloud type."""
    id: str
    name: str
    type_id: int  # EVE type ID for market lookups
    category: str  # fullerite, cytoserocin, mykoserocin
    volume: float  # m3 per unit


@dataclass
class GasSite:
    """A cosmic signature gas site."""
    id: str
    name: str
    region: str = ""  # legacy field
    wh_classes: str = ""  # e.g. "C1-C4", "C5/C6"
    gas_clouds: list[dict] | None = None  # [{gas_id, units}]
    npc_spawn_seconds: int | None = None

    def __post_init__(self):
        if self.gas_clouds is None:
            self.gas_clouds = []


# ---------------------------------------------------------------------------
# Ships
# ---------------------------------------------------------------------------

class ShipRole(str, Enum):
    HARVESTER = "harvester"  # Primary role is mining gas
    BOOSTER = "booster"  # Primary role is fleet boosts
    HYBRID = "hybrid"  # Can both mine and boost (Outrider)


@dataclass
class ShipDef:
    """Definition of a ship that participates in gas ops."""
    id: str
    name: str
    role: ShipRole
    turret_slots: int = 0  # Turret hardpoints (for gas scoops)
    high_slots: int = 0  # Total high slots (for harvesters on barges)
    module_type: str = "scoop"  # "scoop" or "harvester" — which gas modules this ship uses
    ore_hold_m3: float = 0
    cargo_m3: float = 0

    # Gas harvesting bonuses
    role_yield_bonus: float = 0  # Flat % bonus to gas yield (e.g., 100 = +100%)
    yield_bonus_per_level: float = 0  # % bonus to gas yield per skill level
    yield_bonus_skill: str = ""  # Which skill provides the yield bonus
    role_cycle_time_bonus: float = 0  # Flat % reduction to cycle time from role
    cycle_time_bonus_per_level: float = 0  # % reduction per skill level
    cycle_time_bonus_skill: str = ""  # Which skill provides cycle bonus

    # Command burst capability
    can_boost: bool = False
    burst_slots: int = 0
    burst_strength_per_level: float = 0  # % bonus to burst effect per skill level
    burst_strength_skill: str = ""  # Which skill provides burst bonus

    # Special
    can_covert_cloak: bool = False
    notes: str = ""

    @property
    def gas_module_slots(self) -> int:
        """Number of slots available for gas harvesting modules."""
        if self.module_type == "harvester":
            return self.high_slots  # Barges/exhumers use high slots
        return self.turret_slots  # Frigates/destroyers use turret hardpoints


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

@dataclass
class HarvesterModule:
    """A gas cloud harvesting module (scoop)."""
    id: str
    name: str
    yield_per_cycle: float  # m3 per cycle (base)
    cycle_time: float  # seconds (base)
    meta_level: int = 0
    is_abyssal: bool = False  # True for player-customized abyssal modules


@dataclass
class BurstModule:
    """A Mining Foreman Burst module."""
    id: str
    name: str
    base_cycle_time_bonus: float = 0  # % cycle time reduction (Mining Laser Optimization)
    base_yield_bonus: float = 0  # Not typically used for gas, but future-proof


@dataclass
class BurstCharge:
    """A charge for Mining Foreman Burst modules."""
    id: str
    name: str
    effect: str  # "cycle_time" or "yield" or "waste_reduction"
    base_bonus: float = 0  # Base bonus percentage


# ---------------------------------------------------------------------------
# Pilot configuration
# ---------------------------------------------------------------------------

@dataclass
class PilotSkills:
    """All relevant skill levels for a pilot."""
    # Gas harvesting
    gas_cloud_harvesting: int = 0  # 1-5, reduces cycle time
    # Ship operation
    mining_frigate: int = 0  # 1-5, Venture/Prospect yield bonus
    expedition_frigates: int = 0  # 1-5, Prospect prerequisite
    mining_destroyer: int = 0  # 1-5, Pioneer/Outrider yield bonus
    command_destroyers: int = 0  # 1-5, Outrider burst bonus
    expedition_command_ships: int = 0  # 1-5, Odysseus cycle time bonus
    # Boost skills
    mining_director: int = 0  # 1-5, burst strength
    mining_foreman: int = 0  # 1-5, squad/fleet boost range
    # Industrial command
    industrial_command_ships: int = 0  # 1-5, Porpoise/Orca
    capital_industrial_ships: int = 0  # 1-5, Rorqual


@dataclass
class PilotConfig:
    """A single pilot in the fleet."""
    name: str
    ship_id: str  # References ShipDef.id
    skills: PilotSkills = field(default_factory=PilotSkills)
    harvesters: list[HarvesterModule] = field(default_factory=list)
    # Boost config (only if ship can boost)
    active_bursts: list[str] = field(default_factory=list)  # Burst module IDs
    burst_charges: list[str] = field(default_factory=list)  # Charge IDs


# ---------------------------------------------------------------------------
# Fleet and results
# ---------------------------------------------------------------------------

@dataclass
class FleetConfig:
    """A fleet of pilots for gas harvesting."""
    pilots: list[PilotConfig] = field(default_factory=list)


@dataclass
class PilotResult:
    """Harvesting results for a single pilot."""
    pilot_name: str
    ship_name: str
    num_harvesters: int
    yield_per_cycle_m3: float  # Per turret, after all bonuses
    effective_cycle_time: float  # After all bonuses
    m3_per_hour: float
    is_booster: bool = False
    boost_details: str = ""  # Description of active boosts


@dataclass
class FleetResult:
    """Combined fleet harvesting results."""
    pilot_results: list[PilotResult]
    fleet_m3_per_hour: float
    boost_cycle_time_bonus: float  # Total fleet-wide cycle time bonus from boosters
    boost_yield_bonus: float  # Total fleet-wide yield bonus from boosters
    gas_table: list[dict] = field(default_factory=list)
    site_results: list[dict] = field(default_factory=list)
