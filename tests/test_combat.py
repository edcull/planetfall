"""Tests for the Planetfall combat system."""

import pytest
from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType, Zone,
    zone_range_inches, generate_random_terrain,
)
from planetfall.engine.combat.shooting import (
    get_hit_target, resolve_shot, resolve_shooting_action,
    resolve_area_weapon, resolve_stream_weapon,
)
from planetfall.engine.combat.brawling import resolve_brawl
from planetfall.engine.combat.enemy_ai import (
    get_enemy_activation_order, find_best_target, plan_enemy_action,
)
from planetfall.engine.combat.round import (
    roll_reactions, execute_enemy_phase, execute_player_activation,
    check_panic, check_battle_end, reset_round,
)
from planetfall.engine.tables.tactical_enemy_gen import (
    TACTICAL_ENEMY_TABLE, TACTICAL_ENEMY_PROFILES, ENEMY_WEAPONS,
    generate_tactical_enemy_group, roll_number_appearing,
)
from planetfall.engine.tables.lifeform_gen import (
    generate_lifeform, generate_lifeform_group,
)


# --- Helpers ---

def make_battlefield() -> Battlefield:
    """Create a basic battlefield with open terrain."""
    return Battlefield()


def make_player(name="Player 1", zone=(2, 1), **kwargs) -> Figure:
    defaults = dict(
        side=FigureSide.PLAYER, zone=zone, speed=4, reactions=2,
        combat_skill=1, toughness=3, weapon_range=24, weapon_shots=1,
        weapon_damage=0, char_class="trooper", armor_save=5,
    )
    defaults.update(kwargs)
    return Figure(name=name, **defaults)


def make_enemy(name="Enemy 1", zone=(0, 1), **kwargs) -> Figure:
    defaults = dict(
        side=FigureSide.ENEMY, zone=zone, speed=4, reactions=2,
        combat_skill=0, toughness=3, weapon_range=24, weapon_shots=1,
        weapon_damage=0, panic_range=2,
    )
    defaults.update(kwargs)
    return Figure(name=name, **defaults)


# --- Battlefield tests ---

class TestBattlefield:
    def test_default_6x6_grid(self):
        bf = make_battlefield()
        assert len(bf.zones) == 6
        assert len(bf.zones[0]) == 6

    def test_zone_distance_same(self):
        bf = make_battlefield()
        assert bf.zone_distance((1, 1), (1, 1)) == 0

    def test_zone_distance_adjacent(self):
        bf = make_battlefield()
        assert bf.zone_distance((0, 0), (1, 1)) == 1
        assert bf.zone_distance((0, 0), (0, 1)) == 1

    def test_zone_distance_far(self):
        bf = make_battlefield()
        assert bf.zone_distance((0, 0), (2, 2)) == 2

    def test_adjacent_zones(self):
        bf = make_battlefield()
        adj = bf.adjacent_zones(1, 1)
        assert len(adj) == 8  # center has 8 neighbors

    def test_adjacent_zones_corner(self):
        bf = make_battlefield()
        adj = bf.adjacent_zones(0, 0)
        assert len(adj) == 3  # corner has 3 neighbors

    def test_get_figures_in_zone(self):
        bf = make_battlefield()
        p = make_player(zone=(2, 1))
        e = make_enemy(zone=(2, 1))
        bf.figures = [p, e]
        figs = bf.get_figures_in_zone(2, 1)
        assert len(figs) == 2

    def test_zone_range_inches(self):
        assert zone_range_inches(0) == 2   # same zone = close range
        assert zone_range_inches(1) == 4   # 1 zone = 4"
        assert zone_range_inches(2) == 8   # 2 zones = 8"
        assert zone_range_inches(6) == 24  # 6 zones = 24"

    def test_random_terrain(self):
        terrain = generate_random_terrain()
        assert len(terrain) == 6
        assert len(terrain[0]) == 6

    def test_random_terrain_custom_size(self):
        terrain = generate_random_terrain(rows=9, cols=9)
        assert len(terrain) == 9
        assert len(terrain[0]) == 9

    def test_figure_effective_toughness(self):
        f = make_player(toughness=4)
        assert f.effective_toughness == 4
        f.status = FigureStatus.STUNNED
        assert f.effective_toughness == 3
        f.status = FigureStatus.SPRAWLING
        assert f.effective_toughness == 3


# --- Shooting tests ---

class TestShooting:
    def test_hit_target_close_open(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1))
        target = make_enemy(zone=(2, 1))  # same zone
        bf.figures = [shooter, target]
        assert get_hit_target(bf, shooter, target) == 3

    def test_hit_target_medium_open(self):
        bf = make_battlefield()
        shooter = make_player(zone=(5, 1))
        target = make_enemy(zone=(2, 1))  # 3 zones = 12" -> open, >2 zones
        bf.figures = [shooter, target]
        assert get_hit_target(bf, shooter, target) == 5

    def test_hit_target_cover(self):
        bf = make_battlefield()
        bf.zones[0][1].terrain = TerrainType.HEAVY_COVER
        shooter = make_player(zone=(2, 1))
        target = make_enemy(zone=(0, 1))
        bf.figures = [shooter, target]
        assert get_hit_target(bf, shooter, target) == 6

    def test_hit_target_out_of_range(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1), weapon_range=6)
        target = make_enemy(zone=(0, 1))  # 2 zones = 24"
        bf.figures = [shooter, target]
        assert get_hit_target(bf, shooter, target) == 7  # impossible

    def test_resolve_shot_produces_result(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1))
        target = make_enemy(zone=(1, 1))
        bf.figures = [shooter, target]
        result = resolve_shot(bf, shooter, target)
        assert result.shooter == "Player 1"
        assert result.target == "Enemy 1"
        assert result.outcome in ("miss", "casualty", "sprawling", "stunned", "saved")

    def test_shooting_action_multiple_shots(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1), weapon_shots=3)
        target = make_enemy(zone=(1, 1), toughness=6)  # hard to kill
        bf.figures = [shooter, target]
        results = resolve_shooting_action(bf, shooter, target)
        assert len(results) >= 1  # at least attempted

    def test_area_weapon(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1), weapon_traits=["area"], weapon_range=18)
        e1 = make_enemy("E1", zone=(0, 1))
        e2 = make_enemy("E2", zone=(0, 1))
        bf.figures = [shooter, e1, e2]
        results = resolve_area_weapon(bf, shooter, (0, 1))
        assert len(results) == 2  # both enemies targeted

    def test_stream_weapon_auto_hits(self):
        bf = make_battlefield()
        shooter = make_player(zone=(2, 1), weapon_traits=["stream"])
        target = make_enemy(zone=(2, 1))  # same zone
        bf.figures = [shooter, target]
        results = resolve_stream_weapon(bf, shooter, (2, 1))
        # Stream hits all in zone including allies, but at least the enemy
        assert any(r.hit for r in results)


# --- Brawling tests ---

class TestBrawling:
    def test_brawl_produces_result(self):
        bf = make_battlefield()
        attacker = make_player(zone=(1, 1))
        defender = make_enemy(zone=(1, 1))
        bf.figures = [attacker, defender]
        result = resolve_brawl(bf, attacker, defender)
        assert result.winner in ("attacker", "defender", "draw")
        assert result.attacker == "Player 1"
        assert result.defender == "Enemy 1"

    def test_brawl_stunned_bonus(self):
        bf = make_battlefield()
        attacker = make_player(zone=(1, 1), stun_markers=2)
        defender = make_enemy(zone=(1, 1))
        bf.figures = [attacker, defender]
        result = resolve_brawl(bf, attacker, defender)
        # Defender got bonus from attacker's stun markers (cleared on brawl entry)
        # Attacker may gain new stun markers from losing, so check the log instead
        assert any("2 markers" in line for line in result.log)

    def test_brawl_melee_weapon_bonus(self):
        bf = make_battlefield()
        attacker = make_player(zone=(1, 1), weapon_traits=["melee"], melee_damage=2)
        defender = make_enemy(zone=(1, 1))
        bf.figures = [attacker, defender]
        result = resolve_brawl(bf, attacker, defender)
        assert result.attacker_total > 0  # Had weapon bonus applied


# --- Enemy AI tests ---

class TestEnemyAI:
    def test_activation_order(self):
        bf = make_battlefield()
        regular = make_enemy("Regular", zone=(0, 0))
        specialist = make_enemy("Spec", zone=(0, 2), is_specialist=True)
        leader = make_enemy("Leader", zone=(0, 1), is_leader=True)
        bf.figures = [regular, specialist, leader]
        order = get_enemy_activation_order(bf)
        assert order[0].name == "Spec"  # specialist first

    def test_find_best_target(self):
        bf = make_battlefield()
        shooter = make_enemy(zone=(0, 1), weapon_range=24)
        p1 = make_player("P1", zone=(2, 0))
        p2 = make_player("P2", zone=(1, 1))  # closer
        bf.figures = [shooter, p1, p2]
        target = find_best_target(bf, shooter)
        # Should prefer the closer/easier target
        assert target is not None

    def test_plan_enemy_action_shoot(self):
        bf = make_battlefield()
        enemy = make_enemy(zone=(0, 1), weapon_range=24)
        player = make_player(zone=(2, 1))
        bf.figures = [enemy, player]
        action = plan_enemy_action(bf, enemy)
        assert action.action_type in ("shoot", "move_and_shoot", "move")

    def test_plan_stunned_enemy(self):
        bf = make_battlefield()
        enemy = make_enemy(zone=(0, 1), stun_markers=1)
        player = make_player(zone=(2, 1))
        bf.figures = [enemy, player]
        action = plan_enemy_action(bf, enemy)
        # Stunned: move OR attack, not both
        assert action.action_type in ("shoot", "move", "move_to_cover", "hold")


# --- Round tests ---

class TestRound:
    def test_reaction_roll(self):
        bf = make_battlefield()
        p1 = make_player("P1", zone=(2, 0), reactions=3)
        p2 = make_player("P2", zone=(2, 2), reactions=1)
        bf.figures = [p1, p2]
        result = roll_reactions(bf)
        assert len(result.dice_rolled) >= 2
        total = len(result.quick_actors) + len(result.slow_actors)
        assert total == 2

    def test_enemy_phase(self):
        bf = make_battlefield()
        enemy = make_enemy(zone=(0, 1))
        player = make_player(zone=(2, 1))
        bf.figures = [enemy, player]
        results = execute_enemy_phase(bf)
        assert len(results) >= 1
        assert enemy.has_acted

    def test_player_activation_shoot(self):
        bf = make_battlefield()
        player = make_player(zone=(2, 1))
        enemy = make_enemy(zone=(1, 1))
        bf.figures = [player, enemy]
        result = execute_player_activation(
            bf, player, "shoot", target_name="Enemy 1"
        )
        assert result.action_type == "shoot"
        assert player.has_acted

    def test_player_activation_move(self):
        bf = make_battlefield()
        player = make_player(zone=(2, 1))
        bf.figures = [player]
        result = execute_player_activation(
            bf, player, "move", move_to=(1, 1)
        )
        assert player.zone == (1, 1)

    def test_check_battle_end_victory(self):
        bf = make_battlefield()
        player = make_player()
        enemy = make_enemy(status=FigureStatus.CASUALTY)
        bf.figures = [player, enemy]
        assert check_battle_end(bf) == "player_victory"

    def test_check_battle_end_defeat(self):
        bf = make_battlefield()
        player = make_player(status=FigureStatus.CASUALTY)
        enemy = make_enemy()
        bf.figures = [player, enemy]
        assert check_battle_end(bf) == "player_defeat"

    def test_check_battle_end_ongoing(self):
        bf = make_battlefield()
        player = make_player()
        enemy = make_enemy()
        bf.figures = [player, enemy]
        assert check_battle_end(bf) is None

    def test_panic_check(self):
        bf = make_battlefield()
        e1 = make_enemy("E1", zone=(0, 0), panic_range=2)
        e2 = make_enemy("E2", zone=(0, 2), panic_range=2)
        bf.figures = [e1, e2]
        # Force a panic check
        result = check_panic(bf, ["SomeCasualty"])
        assert result is not None
        assert result.roll >= 1

    def test_reset_round(self):
        bf = make_battlefield()
        p = make_player(has_acted=True)
        e = make_enemy(has_acted=True)
        bf.figures = [p, e]
        reset_round(bf)
        assert not p.has_acted
        assert not e.has_acted


# --- Enemy generation tests ---

class TestEnemyGeneration:
    def test_tactical_enemy_table_coverage(self):
        """Verify D100 table covers all values 1-100."""
        covered = set()
        for entry in TACTICAL_ENEMY_TABLE.entries:
            for i in range(entry.low, entry.high + 1):
                assert i not in covered, f"Overlap at {i}"
                covered.add(i)
        assert covered == set(range(1, 101))

    def test_all_profiles_exist(self):
        for entry in TACTICAL_ENEMY_TABLE.entries:
            assert entry.result_id in TACTICAL_ENEMY_PROFILES

    def test_generate_enemy_group(self):
        enemies = generate_tactical_enemy_group("outlaws")
        assert len(enemies) >= 5  # 2d3+3 = min 5
        # Should have at least one specialist
        roles = [e.role for e in enemies]
        assert "specialist" in roles

    def test_generate_random_enemy_group(self):
        enemies = generate_tactical_enemy_group()
        assert len(enemies) >= 4  # minimum from any table

    def test_enemy_weapons_exist(self):
        for key in ["scrap_gun", "colony_rifle", "military_rifle",
                     "auto_rifle", "hunting_rifle", "rattle_gun",
                     "blade", "hand_cannon", "ripper_sword",
                     "shatter_axe", "shotgun"]:
            assert key in ENEMY_WEAPONS

    def test_roll_number_appearing(self):
        count = roll_number_appearing("1d3+5")
        assert 6 <= count <= 8  # 1d3 = 1-3, + 5

    def test_fearless_enemy(self):
        enemies = generate_tactical_enemy_group("converted_recon_team")
        assert all(e.panic_range == 0 for e in enemies)


# --- Lifeform generation tests ---

class TestLifeformGeneration:
    def test_generate_lifeform(self):
        profile = generate_lifeform()
        assert profile.speed in (5, 6, 7)
        assert profile.combat_skill in (0, 1, 2)
        assert profile.toughness in (3, 4, 5)

    def test_generate_lifeform_group(self):
        group = generate_lifeform_group(5)
        assert len(group) == 5
        # All share same profile
        assert all(g.speed == group[0].speed for g in group)

    def test_lifeform_stats_in_bounds(self):
        for _ in range(20):
            profile = generate_lifeform()
            assert 5 <= profile.speed <= 7
            assert 0 <= profile.combat_skill <= 2
            assert 0 <= profile.strike_damage <= 2
            assert 3 <= profile.toughness <= 5
            assert profile.armor_save in (0, 5)
            assert profile.kill_points in (0, 1)


# --- Integration test ---

class TestCombatIntegration:
    def test_auto_battle_runs(self):
        """Test that a full auto-battle can run to completion."""
        from planetfall.engine.combat.missions import setup_mission
        from planetfall.engine.campaign.setup import create_new_campaign
        from planetfall.engine.models import ColonizationAgenda, MissionType

        state = create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.UNITY)
        deployed = [c.name for c in state.characters[:4]]

        mission_setup = setup_mission(
            state, MissionType.INVESTIGATION, deployed, grunt_count=2,
        )

        assert len(mission_setup.battlefield.figures) >= 6  # players + enemies

        from planetfall.engine.steps.step08_mission import run_auto_battle
        result = run_auto_battle(mission_setup)

        assert result.rounds_played >= 1
        assert isinstance(result.victory, bool)
        assert len(result.battle_log) > 0

    def test_step08_execute_with_deployment(self):
        """Test step08 execute with auto-battle."""
        from planetfall.engine.campaign.setup import create_new_campaign
        from planetfall.engine.models import ColonizationAgenda, MissionType
        from planetfall.engine.steps import step08_mission

        state = create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.UNITY)
        deployed = [c.name for c in state.characters[:4]]

        result, events = step08_mission.execute(
            state, MissionType.SKIRMISH, deployed_names=deployed, grunt_count=2,
        )

        assert len(events) == 1
        assert events[0].event_type.value == "combat"
        assert "Mission:" in events[0].description
        assert result.rounds_played >= 1

    def test_step08_execute_stub(self):
        """Test step08 execute without deployment (manual stub)."""
        from planetfall.engine.campaign.setup import create_new_campaign
        from planetfall.engine.models import ColonizationAgenda, MissionType
        from planetfall.engine.steps import step08_mission

        state = create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.UNITY)

        result, events = step08_mission.execute(state, MissionType.PATROL)
        assert "Resolve manually" in events[0].description
