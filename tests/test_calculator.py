"""Tests for fleet-based gas harvesting calculator."""
import pytest

from eve_gas.calculator import (
    calculate_fleet,
    calculate_fleet_boost,
    pilot_cycle_time,
    pilot_m3_per_hour,
    pilot_yield_per_cycle,
)
from eve_gas.data.loader import load_gas_types, load_harvesters, load_scoops, load_ships, load_sites
from eve_gas.models import (
    FleetConfig,
    HarvesterModule,
    PilotConfig,
    PilotSkills,
    ShipDef,
    ShipRole,
)


# --- Fixtures ---

@pytest.fixture
def venture():
    return ShipDef(
        id="venture", name="Venture", role=ShipRole.HARVESTER,
        turret_slots=2, ore_hold_m3=5000,
        role_yield_bonus=100,  # Role: +100% gas yield
        cycle_time_bonus_per_level=5, cycle_time_bonus_skill="mining_frigate",  # -5%/lvl
    )


@pytest.fixture
def prospect():
    return ShipDef(
        id="prospect", name="Prospect", role=ShipRole.HARVESTER,
        turret_slots=2, ore_hold_m3=10000,
        role_yield_bonus=100,
        cycle_time_bonus_per_level=5, cycle_time_bonus_skill="mining_frigate",
        can_covert_cloak=True,
    )


@pytest.fixture
def pioneer():
    return ShipDef(
        id="pioneer", name="Pioneer", role=ShipRole.HARVESTER,
        turret_slots=3, ore_hold_m3=8000,
        role_cycle_time_bonus=25,  # Role: -25%
        cycle_time_bonus_per_level=5, cycle_time_bonus_skill="mining_destroyer",
    )


@pytest.fixture
def outrider():
    return ShipDef(
        id="outrider", name="Outrider", role=ShipRole.HYBRID,
        turret_slots=3, ore_hold_m3=20000,
        cycle_time_bonus_per_level=5, cycle_time_bonus_skill="mining_destroyer",
        can_boost=True, burst_slots=1,
        burst_strength_per_level=2, burst_strength_skill="command_destroyers",
    )


@pytest.fixture
def odysseus():
    return ShipDef(
        id="odysseus", name="Odysseus", role=ShipRole.HARVESTER,
        turret_slots=5, cargo_m3=750,
        cycle_time_bonus_per_level=5, cycle_time_bonus_skill="expedition_command_ships",
        can_covert_cloak=True,
    )


@pytest.fixture
def porpoise():
    return ShipDef(
        id="porpoise", name="Porpoise", role=ShipRole.BOOSTER,
        turret_slots=0, ore_hold_m3=50000,
        can_boost=True, burst_slots=2,
        burst_strength_per_level=3, burst_strength_skill="industrial_command_ships",
    )


@pytest.fixture
def scoop_i():
    return HarvesterModule(id="gas_scoop_i", name="Gas Cloud Scoop I", yield_per_cycle=10.0, cycle_time=30.0)


@pytest.fixture
def scoop_ii():
    return HarvesterModule(id="gas_scoop_ii", name="Gas Cloud Scoop II", yield_per_cycle=10.0, cycle_time=30.0)


# --- Cycle Time Tests ---

class TestCycleTime:
    def test_no_skills(self, venture, scoop_i):
        ct = pilot_cycle_time(scoop_i, venture, PilotSkills())
        assert ct == 30.0  # No role cycle bonus on Venture, no skills

    def test_venture_mf5(self, venture, scoop_i):
        skills = PilotSkills(mining_frigate=5)
        ct = pilot_cycle_time(scoop_i, venture, skills)
        # 30 * (1 - 5*0.05) = 30 * 0.75 = 22.5
        assert ct == pytest.approx(22.5)

    def test_pioneer_role_bonus(self, pioneer, scoop_i):
        # Pioneer has -25% role bonus + -5%/lvl
        skills = PilotSkills(mining_destroyer=5)
        ct = pilot_cycle_time(scoop_i, pioneer, skills)
        # 30 * 0.75 (role) * 0.75 (5*5%) = 30 * 0.5625 = 16.875
        assert ct == pytest.approx(16.875)

    def test_pioneer_role_only(self, pioneer, scoop_i):
        ct = pilot_cycle_time(scoop_i, pioneer, PilotSkills())
        # 30 * 0.75 (role) = 22.5
        assert ct == pytest.approx(22.5)

    def test_odysseus_cycle_bonus(self, odysseus, scoop_i):
        skills = PilotSkills(expedition_command_ships=5)
        ct = pilot_cycle_time(scoop_i, odysseus, skills)
        # 30 * (1 - 5*0.05) = 30 * 0.75 = 22.5
        assert ct == pytest.approx(22.5)

    def test_fleet_boost(self, venture, scoop_i):
        skills = PilotSkills(mining_frigate=5)
        ct = pilot_cycle_time(scoop_i, venture, skills, fleet_cycle_bonus=0.15)
        # 30 * 0.75 (skill) * 0.85 (fleet) = 19.125
        assert ct == pytest.approx(19.125)


# --- Yield Tests ---

class TestYield:
    def test_venture_role_bonus(self, venture, scoop_i):
        # Venture has flat +100% role bonus regardless of skills
        ypc = pilot_yield_per_cycle(scoop_i, venture, PilotSkills())
        assert ypc == pytest.approx(20.0)  # 10 * (1 + 100/100)

    def test_venture_with_syndicate(self, venture):
        syndicate = HarvesterModule(id="syn", name="Syndicate", yield_per_cycle=20.0, cycle_time=30.0)
        ypc = pilot_yield_per_cycle(syndicate, venture, PilotSkills())
        assert ypc == pytest.approx(40.0)  # 20 * 2.0

    def test_pioneer_no_yield_bonus(self, pioneer, scoop_i):
        # Pioneer has cycle time bonuses only, no yield bonus
        ypc = pilot_yield_per_cycle(scoop_i, pioneer, PilotSkills())
        assert ypc == 10.0

    def test_outrider_no_yield_bonus(self, outrider, scoop_i):
        # Outrider has no yield bonus for gas (just cycle time + boost)
        ypc = pilot_yield_per_cycle(scoop_i, outrider, PilotSkills())
        assert ypc == 10.0

    def test_odysseus_no_yield_bonus(self, odysseus, scoop_i):
        ypc = pilot_yield_per_cycle(scoop_i, odysseus, PilotSkills())
        assert ypc == 10.0


# --- M3/Hour Tests ---

class TestM3PerHour:
    def test_venture_full_skills(self, venture, scoop_i):
        skills = PilotSkills(mining_frigate=5)
        rate = pilot_m3_per_hour(venture, [scoop_i, scoop_i], skills)
        # Yield: 10 * 2.0 (role) = 20 m3/cycle
        # Cycle: 30 * 0.75 (5*5%) = 22.5s
        # Per turret: 20 * (3600/22.5) = 3200, x2 = 6400
        assert rate == pytest.approx(6400.0)

    def test_venture_syndicate_scoop(self, venture):
        syndicate = HarvesterModule(id="syn", name="Syndicate", yield_per_cycle=20.0, cycle_time=30.0)
        skills = PilotSkills(mining_frigate=5)
        rate = pilot_m3_per_hour(venture, [syndicate, syndicate], skills)
        # Yield: 20 * 2.0 = 40 m3/cycle, Cycle: 22.5s
        # Per turret: 40 * 160 = 6400, x2 = 12800
        assert rate == pytest.approx(12800.0)

    def test_odysseus_5_turrets(self, odysseus, scoop_i):
        skills = PilotSkills(expedition_command_ships=5)
        harvesters = [scoop_i] * 5
        rate = pilot_m3_per_hour(odysseus, harvesters, skills)
        # Yield: 10 m3/cycle (no yield bonus), Cycle: 30 * 0.75 = 22.5s
        # Per turret: 10 * (3600/22.5) = 1600, x5 = 8000
        assert rate == pytest.approx(8000.0)

    def test_respects_turret_limit(self, venture, scoop_i):
        skills = PilotSkills(mining_frigate=5)
        rate = pilot_m3_per_hour(venture, [scoop_i] * 5, skills)
        rate2 = pilot_m3_per_hour(venture, [scoop_i] * 2, skills)
        assert rate == rate2  # Only 2 should be used


# --- Fleet Boost Tests ---

class TestFleetBoost:
    def test_no_boosters(self):
        pilots = [PilotConfig(name="Solo", ship_id="venture")]
        ships = {"venture": ShipDef(id="venture", name="Venture", role=ShipRole.HARVESTER, turret_slots=2)}
        cycle, yld, descs = calculate_fleet_boost(pilots, ships)
        assert cycle == 0
        assert yld == 0

    def test_porpoise_boost(self, porpoise):
        pilot = PilotConfig(
            name="Booster", ship_id="porpoise",
            skills=PilotSkills(industrial_command_ships=5, mining_director=5),
            active_bursts=["mining_foreman_burst_i"],
        )
        ships = {"porpoise": porpoise}
        cycle, yld, descs = calculate_fleet_boost([pilot], ships)
        # Base 15% * (1 + 0.15 ship + 0.50 director) = 15% * 1.65 = 24.75%
        assert cycle == pytest.approx(0.2475)
        assert len(descs) == 1

    def test_outrider_boost(self, outrider):
        pilot = PilotConfig(
            name="Booster", ship_id="outrider",
            skills=PilotSkills(command_destroyers=5, mining_director=5),
            active_bursts=["mining_foreman_burst_i"],
        )
        ships = {"outrider": outrider}
        cycle, yld, descs = calculate_fleet_boost([pilot], ships)
        # Base 15% * (1 + 0.10 ship + 0.50 director) = 15% * 1.60 = 24.0%
        assert cycle == pytest.approx(0.24)

    def test_best_boost_wins(self, porpoise, outrider):
        p1 = PilotConfig(name="Porpoise", ship_id="porpoise",
                         skills=PilotSkills(industrial_command_ships=5, mining_director=5),
                         active_bursts=["burst"])
        p2 = PilotConfig(name="Outrider", ship_id="outrider",
                         skills=PilotSkills(command_destroyers=5, mining_director=3),
                         active_bursts=["burst"])
        ships = {"porpoise": porpoise, "outrider": outrider}
        cycle, _, _ = calculate_fleet_boost([p1, p2], ships)
        # Porpoise: 15% * (1 + 0.15 + 0.50) = 24.75%
        # Outrider: 15% * (1 + 0.10 + 0.30) = 21.0%
        # Best wins
        assert cycle == pytest.approx(0.2475)


# --- Full Fleet Test ---

class TestFleetCalculation:
    def test_solo_venture(self, venture, scoop_i):
        fleet = FleetConfig(pilots=[
            PilotConfig(
                name="Solo", ship_id="venture",
                skills=PilotSkills(mining_frigate=5),
                harvesters=[scoop_i, scoop_i],
            ),
        ])
        ships = {"venture": venture}
        gas_types = load_gas_types()
        result = calculate_fleet(fleet, ships, gas_types, {})
        assert len(result.pilot_results) == 1
        assert result.fleet_m3_per_hour == pytest.approx(6400.0)
        assert result.boost_cycle_time_bonus == 0

    def test_fleet_with_booster(self, venture, porpoise, scoop_i):
        fleet = FleetConfig(pilots=[
            PilotConfig(
                name="Miner1", ship_id="venture",
                skills=PilotSkills(mining_frigate=5),
                harvesters=[scoop_i, scoop_i],
            ),
            PilotConfig(
                name="Miner2", ship_id="venture",
                skills=PilotSkills(mining_frigate=5),
                harvesters=[scoop_i, scoop_i],
            ),
            PilotConfig(
                name="Booster", ship_id="porpoise",
                skills=PilotSkills(industrial_command_ships=5, mining_director=5),
                active_bursts=["mining_foreman_burst_i"],
            ),
        ])
        ships = {"venture": venture, "porpoise": porpoise}
        gas_types = load_gas_types()
        result = calculate_fleet(fleet, ships, gas_types, {})

        assert len(result.pilot_results) == 3
        assert result.boost_cycle_time_bonus == pytest.approx(0.2475)
        # Boosted duo should harvest more than unboosted duo (6400 * 2)
        assert result.fleet_m3_per_hour > 6400 * 2


# --- Abyssal Module Tests ---

class TestBargeHarvesters:
    def test_hulk_with_t2_harvesters(self):
        hulk = ShipDef(
            id="hulk", name="Hulk", role=ShipRole.HARVESTER,
            high_slots=2, module_type="harvester",
        )
        harvester_ii = HarvesterModule(id="h2", name="Gas Cloud Harvester II", yield_per_cycle=100.0, cycle_time=80.0)
        skills = PilotSkills()  # No special gas bonuses on exhumers
        rate = pilot_m3_per_hour(hulk, [harvester_ii, harvester_ii], skills)
        # 100 m3/cycle, 80s cycle, 2 harvesters
        # Per harvester: 100 * (3600/80) = 4500, x2 = 9000
        assert rate == pytest.approx(9000.0)

    def test_hulk_with_ore_harvester(self):
        hulk = ShipDef(
            id="hulk", name="Hulk", role=ShipRole.HARVESTER,
            high_slots=2, module_type="harvester",
        )
        ore_h = HarvesterModule(id="ore", name="ORE Gas Cloud Harvester", yield_per_cycle=100.0, cycle_time=80.0)
        rate = pilot_m3_per_hour(hulk, [ore_h, ore_h], PilotSkills())
        assert rate == pytest.approx(9000.0)

    def test_procurer_single_harvester(self):
        proc = ShipDef(
            id="procurer", name="Procurer", role=ShipRole.HARVESTER,
            high_slots=2, module_type="harvester",
        )
        h1 = HarvesterModule(id="h1", name="Gas Cloud Harvester I", yield_per_cycle=50.0, cycle_time=100.0)
        # Only 1 harvester in 2 slots
        rate = pilot_m3_per_hour(proc, [h1], PilotSkills())
        # 50 * (3600/100) = 1800
        assert rate == pytest.approx(1800.0)


class TestAbyssalModules:
    def test_custom_abyssal_stats(self, venture):
        abyssal = HarvesterModule(
            id="abyssal_1", name="Abyssal Gas Scoop",
            yield_per_cycle=25.0, cycle_time=27.0, is_abyssal=True,
        )
        skills = PilotSkills(mining_frigate=5)
        rate = pilot_m3_per_hour(venture, [abyssal, abyssal], skills)
        # Yield: 25 * 2.0 (role) = 50 m3/cycle
        # Cycle: 27 * 0.75 (MF5) = 20.25s
        # Per turret: 50 * 3600/20.25 = 8888.9, x2 = 17777.8
        assert rate == pytest.approx(17777.8, rel=0.01)

    def test_mixed_modules(self, venture):
        scoop = HarvesterModule(id="s1", name="Gas Cloud Scoop I", yield_per_cycle=10.0, cycle_time=30.0)
        abyssal = HarvesterModule(id="a1", name="Abyssal Scoop", yield_per_cycle=25.0, cycle_time=25.0, is_abyssal=True)
        skills = PilotSkills(mining_frigate=5)
        rate = pilot_m3_per_hour(venture, [scoop, abyssal], skills)
        scoop_only = pilot_m3_per_hour(venture, [scoop, scoop], skills)
        assert rate > scoop_only


# --- Data Loading Tests ---

class TestDataLoading:
    def test_load_ships(self):
        ships = load_ships()
        assert "venture" in ships
        assert "prospect" in ships
        assert "pioneer" in ships
        assert "outrider" in ships
        assert "odysseus" in ships
        assert "porpoise" in ships
        assert "orca" in ships
        assert "rorqual" in ships
        # Barges and exhumers
        assert "procurer" in ships
        assert "hulk" in ships
        assert len(ships) >= 15

    def test_pioneer_cannot_boost(self):
        ships = load_ships()
        assert not ships["pioneer"].can_boost
        assert not ships["pioneer_ci"].can_boost

    def test_load_scoops(self):
        scoops = load_scoops()
        assert len(scoops) >= 4
        names = [h.name for h in scoops]
        assert "Gas Cloud Scoop I" in names
        assert "Syndicate Gas Cloud Scoop" in names
        syn = next(h for h in scoops if "syndicate" in h.name.lower())
        assert syn.yield_per_cycle == 20.0
        assert syn.cycle_time == 30.0

    def test_load_harvesters(self):
        harvesters = load_harvesters()
        assert len(harvesters) >= 3
        names = [h.name for h in harvesters]
        assert "Gas Cloud Harvester I" in names
        assert "Gas Cloud Harvester II" in names
        assert "ORE Gas Cloud Harvester" in names
        h1 = next(h for h in harvesters if h.id == "gas_harvester_i")
        assert h1.yield_per_cycle == 50.0
        assert h1.cycle_time == 100.0

    def test_load_gas_types(self):
        gas_types = load_gas_types()
        assert len(gas_types) >= 20
        categories = {g.category for g in gas_types}
        assert "fullerite" in categories

    def test_load_sites(self):
        sites = load_sites()
        assert len(sites) >= 5

    def test_ship_roles(self):
        ships = load_ships()
        assert ships["venture"].role == ShipRole.HARVESTER
        assert ships["outrider"].role == ShipRole.HYBRID
        assert ships["porpoise"].role == ShipRole.BOOSTER

    def test_ship_module_types(self):
        ships = load_ships()
        assert ships["venture"].module_type == "scoop"
        assert ships["hulk"].module_type == "harvester"
        assert ships["procurer"].module_type == "harvester"

    def test_barge_gas_slots(self):
        ships = load_ships()
        # Barges have 2 high slots for harvesters, 0 turret hardpoints
        assert ships["procurer"].high_slots == 2
        assert ships["procurer"].turret_slots == 0
        assert ships["procurer"].gas_module_slots == 2

    def test_venture_gas_slots(self):
        ships = load_ships()
        assert ships["venture"].turret_slots == 2
        assert ships["venture"].gas_module_slots == 2

    def test_outrider_can_boost(self):
        ships = load_ships()
        assert ships["outrider"].can_boost
        assert ships["outrider"].burst_slots == 1
        assert ships["outrider"].burst_strength_per_level == 2

    def test_odysseus_cycle_bonus(self):
        ships = load_ships()
        assert ships["odysseus"].cycle_time_bonus_per_level == 5
        assert ships["odysseus"].turret_slots == 5
        assert ships["odysseus"].can_covert_cloak
