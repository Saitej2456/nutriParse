from __future__ import annotations

import pytest

from src.nutri_score import (
    ENERGY_POINTS,
    FIBER_POINTS,
    PROTEIN_POINTS,
    SATURATED_FAT_POINTS,
    SODIUM_POINTS,
    SUGAR_POINTS,
    KCAL_TO_KJ,
    NutriScoreCalculator,
    _points_for,
)


def stage3_input(**nutrition_overrides):
    nutrition = {
        "calories_kcal": 100,
        "total_sugars_g": 2,
        "saturated_fat_g": 0.5,
        "sodium_mg": 50,
        "fiber_g": 1,
        "protein_g": 2,
    }
    nutrition.update(nutrition_overrides)
    return {
        "normalized": {
            "basis": {"type": "per_100g", "amount": 100, "unit": "g"},
            "normalization_possible": True,
            "nutrition": nutrition,
        }
    }


@pytest.mark.parametrize(
    ("table", "boundary", "points"),
    [
        (ENERGY_POINTS, 335, 0),
        (SUGAR_POINTS, 4.5, 0),
        (SATURATED_FAT_POINTS, 1, 0),
        (SODIUM_POINTS, 90, 0),
        (FIBER_POINTS, 0.9, 0),
        (PROTEIN_POINTS, 1.6, 0),
    ],
)
def test_first_boundary_and_adjacent_values(table, boundary, points):
    assert _points_for(boundary - 0.0001, table) == points
    assert _points_for(boundary, table) == points
    assert _points_for(boundary + 0.0001, table) == points + 1


@pytest.mark.parametrize(
    ("table", "boundaries"),
    [
        (ENERGY_POINTS, [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]),
        (SUGAR_POINTS, [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]),
        (SATURATED_FAT_POINTS, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        (SODIUM_POINTS, [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]),
        (FIBER_POINTS, [0.9, 1.9, 2.8, 3.7, 4.7]),
        (PROTEIN_POINTS, [1.6, 3.2, 4.8, 6.4, 8]),
    ],
)
def test_every_table_boundary_and_its_adjacent_values(table, boundaries):
    for expected_points, boundary in enumerate(boundaries):
        assert _points_for(boundary - 0.0001, table) == expected_points
        assert _points_for(boundary, table) == expected_points
        assert _points_for(boundary + 0.0001, table) == expected_points + 1


def test_kcal_is_converted_to_kj_for_energy_lookup():
    result = NutriScoreCalculator().calculate(stage3_input(calories_kcal=400))
    energy = result["negative_points"]["energy"]
    assert energy["input_value"] == pytest.approx(400 * KCAL_TO_KJ)
    assert energy["points"] == 4
    assert energy["source_input_value"] == 400


def test_component_points_are_reported():
    result = NutriScoreCalculator().calculate(
        stage3_input(calories_kcal=400, total_sugars_g=14.2857, saturated_fat_g=5, sodium_mg=450, fiber_g=4.7, protein_g=8)
    )
    assert result["negative_points"]["energy"]["points"] == 4
    assert result["negative_points"]["sugars"]["points"] == 3
    assert result["negative_points"]["saturated_fat"]["points"] == 4
    assert result["negative_points"]["sodium"]["points"] == 4
    assert result["positive_points"]["fiber"]["points"] == 4
    assert result["positive_points"]["protein"]["points"] == 4


def test_fvln_is_explicitly_unavailable_not_zero_percent():
    result = NutriScoreCalculator().calculate(stage3_input())
    fvln = result["positive_points"]["fruit_vegetable_legume_nut"]
    assert fvln == {
        "available": False,
        "points": 0,
        "reason": "FVLN percentage unavailable from extracted nutrition data",
    }
    assert result["calculation_complete"] is False
    assert any("FVLN percentage unavailable" in warning for warning in result["warnings"])


def test_final_score_and_grade_for_end_to_end_stage3_example():
    result = NutriScoreCalculator().calculate(
        stage3_input(
            calories_kcal=400,
            total_sugars_g=14.2857,
            saturated_fat_g=0,
            sodium_mg=0,
            fiber_g=11.4286,
            protein_g=11.4286,
        )
    )
    assert result["negative_points"]["total"] == 7
    assert result["positive_points"]["total"] == 10
    assert result["final_score"] == -3
    assert result["grade"] == "A"
    assert result["score_available"] is True


@pytest.mark.parametrize(
    ("score", "grade"),
    [(-100, "A"), (-1, "A"), (0, "B"), (2, "B"), (3, "C"), (10, "C"), (11, "D"), (18, "D"), (19, "E")],
)
def test_old_general_food_grade_boundaries(score, grade):
    assert NutriScoreCalculator._grade_for(score) == grade


def test_protein_is_excluded_when_negative_points_at_least_eleven_and_fvln_below_five():
    result = NutriScoreCalculator().calculate(
        stage3_input(calories_kcal=400, total_sugars_g=45.1, saturated_fat_g=0, sodium_mg=0, fiber_g=0, protein_g=9)
    )
    assert result["negative_points"]["total"] == 14
    assert result["positive_points"]["protein"]["points"] == 5
    assert result["positive_points"]["protein"]["included_in_final_score"] is False
    assert result["positive_points"]["total"] == 0
    assert result["final_score"] == 14


def test_missing_value_does_not_become_zero_or_produce_grade():
    result = NutriScoreCalculator().calculate(stage3_input(sodium_mg=None))
    assert result["negative_points"]["sodium"]["points"] is None
    assert result["negative_points"]["total"] is None
    assert result["final_score"] is None
    assert result["grade"] is None
    assert result["score_available"] is False


def test_unsupported_basis_is_not_scored():
    data = stage3_input()
    data["normalized"]["basis"]["type"] = "per_100ml"
    result = NutriScoreCalculator().calculate(data)
    assert result["score_available"] is False
    assert result["final_score"] is None
    assert any("per_100g" in warning for warning in result["warnings"])
