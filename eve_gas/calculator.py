"""Fleet-based gas harvesting yield and profitability calculations."""
import math

from .models import (
    BurstCharge,
    FleetConfig,
    FleetResult,
    GasSite,
    GasType,
    HarvesterModule,
    PilotConfig,
    PilotResult,
    PilotSkills,
    ShipDef,
)


def pilot_cycle_time(
    module: HarvesterModule,
    ship: ShipDef,
    skills: PilotSkills,
    fleet_cycle_bonus: float = 0,
) -> float:
    """Calculate effective cycle time for a pilot's gas scoop.

    Bonuses applied (stacking penalized where noted):
    1. Gas Cloud Harvesting skill: -10% per level (multiplicative)
    2. Ship cycle time bonus (e.g., Odysseus -5%/lvl) (multiplicative)
    3. Fleet burst cycle time bonus (multiplicative)

    Args:
        module: The gas harvester module.
        ship: The ship definition.
        skills: Pilot's skill levels.
        fleet_cycle_bonus: Fleet-wide cycle time reduction from booster (0-1 as fraction).

    Returns:
        Effective cycle time in seconds.
    """
    base = module.cycle_time

    # Ship role cycle time bonus (flat, e.g., Pioneer: -25%)
    role_mult = 1 - (ship.role_cycle_time_bonus / 100) if ship.role_cycle_time_bonus > 0 else 1.0

    # Ship per-level cycle time bonus (e.g., -5% per Mining Frigate level)
    skill_mult = 1.0
    if ship.cycle_time_bonus_per_level > 0 and ship.cycle_time_bonus_skill:
        skill_level = _get_skill_level(skills, ship.cycle_time_bonus_skill)
        skill_mult = 1 - (ship.cycle_time_bonus_per_level / 100 * skill_level)

    # Fleet boost (from Mining Laser Optimization charge)
    fleet_mult = 1 - fleet_cycle_bonus

    return base * role_mult * skill_mult * fleet_mult


def pilot_yield_per_cycle(
    module: HarvesterModule,
    ship: ShipDef,
    skills: PilotSkills,
) -> float:
    """Calculate yield per cycle per turret for a pilot.

    Ship yield bonus (e.g., Venture +100%/lvl Mining Frigate) applied.

    Args:
        module: The gas harvester module.
        ship: The ship definition.
        skills: Pilot's skill levels.

    Returns:
        m3 per cycle per turret.
    """
    base = module.yield_per_cycle

    # Ship role yield bonus (flat, e.g., Venture/Prospect: +100%)
    if ship.role_yield_bonus > 0:
        base *= (1 + ship.role_yield_bonus / 100)

    # Ship per-level yield bonus (if any)
    if ship.yield_bonus_per_level > 0 and ship.yield_bonus_skill:
        skill_level = _get_skill_level(skills, ship.yield_bonus_skill)
        base *= (1 + ship.yield_bonus_per_level / 100 * skill_level)

    return base


def pilot_m3_per_hour(
    ship: ShipDef,
    harvesters: list[HarvesterModule],
    skills: PilotSkills,
    fleet_cycle_bonus: float = 0,
) -> float:
    """Calculate total m3/hour for a pilot across all their harvesters.

    Each harvester can be a different module (supports abyssal mix).
    """
    total = 0.0
    for module in harvesters[:ship.gas_module_slots]:
        ypc = pilot_yield_per_cycle(module, ship, skills)
        cycle = pilot_cycle_time(module, ship, skills, fleet_cycle_bonus)
        if cycle > 0:
            total += ypc * (3600 / cycle)
    return total


def calculate_fleet_boost(
    pilots: list[PilotConfig],
    ships: dict[str, ShipDef],
) -> tuple[float, float, list[str]]:
    """Calculate the total fleet-wide boost from all boosting pilots.

    Mining Foreman Burst with Mining Laser Optimization charge reduces cycle time.
    Boost strength depends on:
    - Base charge bonus (15% for Mining Laser Optimization)
    - Ship burst strength bonus per skill level
    - Mining Director skill (+10% per level to burst effect strength)
    - T2 Mining Foreman Burst module (+25% effect strength)
    - Mining Foreman Mindlink / ORE Mining Director Mindlink (+25% effect strength)

    Only the strongest boost applies (boosts don't stack from multiple boosters).

    Returns:
        (cycle_time_bonus as fraction 0-1, yield_bonus as fraction, boost descriptions)
    """
    best_cycle_bonus = 0.0
    best_yield_bonus = 0.0
    descriptions = []

    for pilot in pilots:
        ship = ships.get(pilot.ship_id)
        if not ship or not ship.can_boost:
            continue
        if not pilot.active_bursts:
            continue

        # Base charge bonus (Mining Laser Optimization = 15% cycle time reduction)
        base_bonus = 0.15

        # Ship burst strength bonus per level
        ship_bonus = 0.0
        if ship.burst_strength_per_level > 0 and ship.burst_strength_skill:
            skill_level = _get_skill_level(pilot.skills, ship.burst_strength_skill)
            ship_bonus = ship.burst_strength_per_level / 100 * skill_level

        # Mining Director skill: +10% per level
        director_bonus = 0.10 * pilot.skills.mining_director

        # T2 Mining Foreman Burst module: +25% effect strength
        t2_module_mult = 1.25 if pilot.burst_module_t2 else 1.0

        # Mindlink implant: +25% effect strength
        mindlink_mult = 1.25 if pilot.has_mindlink else 1.0

        # All bonuses multiply together
        cycle_bonus = base_bonus * (1 + ship_bonus + director_bonus) * t2_module_mult * mindlink_mult

        if cycle_bonus > best_cycle_bonus:
            best_cycle_bonus = cycle_bonus
            parts = [f"{pilot.name} ({ship.name}): -{cycle_bonus*100:.1f}% cycle time"]
            if pilot.burst_module_t2:
                parts.append("T2 burst")
            if pilot.has_mindlink:
                parts.append("Mindlink")
            descriptions = [", ".join(parts)]

    return best_cycle_bonus, best_yield_bonus, descriptions


def calculate_fleet(
    fleet: FleetConfig,
    ships: dict[str, ShipDef],
    gas_types: list[GasType],
    prices: dict[str, float],
    sites: list[GasSite] | None = None,
) -> FleetResult:
    """Calculate fleet-wide gas harvesting results.

    Args:
        fleet: Fleet configuration with all pilots.
        ships: Ship definitions lookup.
        gas_types: All gas type definitions.
        prices: Gas prices (gas_id -> ISK per unit).
        sites: Optional gas sites for site value calculations.

    Returns:
        FleetResult with per-pilot and fleet-wide results.
    """
    # Step 1: Calculate fleet-wide boost
    cycle_bonus, yield_bonus, boost_descs = calculate_fleet_boost(fleet.pilots, ships)

    # Step 2: Calculate each pilot's harvesting rate
    pilot_results = []
    fleet_m3_per_hour = 0.0

    for pilot in fleet.pilots:
        ship = ships.get(pilot.ship_id)
        if not ship:
            continue

        num_harvesters = min(len(pilot.harvesters), ship.gas_module_slots)
        if num_harvesters == 0 and ship.gas_module_slots == 0:
            # Pure booster ship
            pilot_results.append(PilotResult(
                pilot_name=pilot.name,
                ship_name=ship.name,
                num_harvesters=0,
                yield_per_cycle_m3=0,
                effective_cycle_time=0,
                m3_per_hour=0,
                is_booster=ship.can_boost and len(pilot.active_bursts) > 0,
                boost_details="; ".join(boost_descs) if ship.can_boost and pilot.active_bursts else "",
            ))
            continue

        # Use first harvester for display stats (they may differ for abyssal)
        display_module = pilot.harvesters[0] if pilot.harvesters else None
        m3_hr = pilot_m3_per_hour(ship, pilot.harvesters, pilot.skills, cycle_bonus)
        fleet_m3_per_hour += m3_hr

        ypc = pilot_yield_per_cycle(display_module, ship, pilot.skills) if display_module else 0
        cycle = pilot_cycle_time(display_module, ship, pilot.skills, cycle_bonus) if display_module else 0

        pilot_results.append(PilotResult(
            pilot_name=pilot.name,
            ship_name=ship.name,
            num_harvesters=num_harvesters,
            yield_per_cycle_m3=ypc,
            effective_cycle_time=cycle,
            m3_per_hour=m3_hr,
            is_booster=ship.can_boost and len(pilot.active_bursts) > 0,
            boost_details="; ".join(boost_descs) if ship.can_boost and pilot.active_bursts else "",
        ))

    # Step 3: Gas profitability table (fleet-wide)
    gas_table = []
    for gas in gas_types:
        price = prices.get(gas.id, 0)
        units_per_hour = fleet_m3_per_hour / gas.volume if gas.volume > 0 else 0
        iph = units_per_hour * price
        gas_table.append({
            "gas_id": gas.id,
            "gas_name": gas.name,
            "category": gas.category,
            "price_per_unit": price,
            "isk_per_m3": price / gas.volume if gas.volume > 0 else 0,
            "isk_per_hour": iph,
            "units_per_hour": units_per_hour,
        })
    gas_table.sort(key=lambda x: x["isk_per_hour"], reverse=True)

    # Step 4: Site value calculations
    site_results = []
    if sites and fleet_m3_per_hour > 0:
        gas_lookup = {g.id: g for g in gas_types}
        for site in sites:
            result = _site_value(site, gas_lookup, fleet_m3_per_hour, prices)
            site_results.append(result)
        site_results.sort(key=lambda x: x["total_isk"], reverse=True)

    return FleetResult(
        pilot_results=pilot_results,
        fleet_m3_per_hour=fleet_m3_per_hour,
        boost_cycle_time_bonus=cycle_bonus,
        boost_yield_bonus=yield_bonus,
        gas_table=gas_table,
        site_results=site_results,
    )


def _site_value(
    site: GasSite,
    gas_types: dict[str, GasType],
    fleet_m3_per_hour: float,
    prices: dict[str, float],
) -> dict:
    """Calculate fleet ISK from a gas site before NPC spawn."""
    m3_per_second = fleet_m3_per_hour / 3600

    total_volume = 0.0
    for cloud in site.gas_clouds:
        gas = gas_types.get(cloud["gas_id"])
        if gas:
            total_volume += cloud["units"] * gas.volume

    time_to_clear = total_volume / m3_per_second if m3_per_second > 0 else float("inf")

    time_limited = False
    if site.npc_spawn_seconds and site.npc_spawn_seconds < time_to_clear:
        effective_time = site.npc_spawn_seconds
        time_limited = True
    else:
        effective_time = time_to_clear

    harvestable_m3 = m3_per_second * effective_time

    breakdown = []
    total_isk = 0.0
    for cloud in site.gas_clouds:
        gas = gas_types.get(cloud["gas_id"])
        if not gas:
            continue
        cloud_volume = cloud["units"] * gas.volume
        proportion = cloud_volume / total_volume if total_volume > 0 else 0
        harvested_volume = min(harvestable_m3 * proportion, cloud_volume)
        units = harvested_volume / gas.volume if gas.volume > 0 else 0
        price = prices.get(cloud["gas_id"], 0)
        value = units * price
        total_isk += value
        breakdown.append({
            "gas_id": cloud["gas_id"],
            "name": gas.name,
            "total_units": cloud["units"],
            "harvestable_units": round(units),
            "isk_value": value,
        })

    return {
        "site_name": site.name,
        "region": site.region,
        "total_isk": total_isk,
        "harvest_time_seconds": effective_time,
        "time_limited": time_limited,
        "gas_breakdown": breakdown,
    }


def _get_skill_level(skills: PilotSkills, skill_name: str) -> int:
    """Get a skill level from a PilotSkills object by attribute name."""
    return getattr(skills, skill_name, 0)
