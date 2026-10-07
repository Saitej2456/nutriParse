"""Stage 4: deterministic original Nutri-Score calculation for general foods.

This module intentionally implements the pre-2023 Nutri-Score convention only.
It consumes the Stage-3 serialized normalization output; it does not alter
extraction, parsing, or normalization data.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


KCAL_TO_KJ = 4.184

# The entries are inclusive upper bounds.  A value larger than the final
# upper bound receives the final point value.
ENERGY_POINTS: tuple[tuple[float, int], ...] = (
    (335, 0), (670, 1), (1005, 2), (1340, 3), (1675, 4),
    (2010, 5), (2345, 6), (2680, 7), (3015, 8), (3350, 9),
    (math.inf, 10),
)
SUGAR_POINTS: tuple[tuple[float, int], ...] = (
    (4.5, 0), (9, 1), (13.5, 2), (18, 3), (22.5, 4),
    (27, 5), (31, 6), (36, 7), (40, 8), (45, 9), (math.inf, 10),
)
SATURATED_FAT_POINTS: tuple[tuple[float, int], ...] = (
    (1, 0), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5),
    (7, 6), (8, 7), (9, 8), (10, 9), (math.inf, 10),
)
SODIUM_POINTS: tuple[tuple[float, int], ...] = (
    (90, 0), (180, 1), (270, 2), (360, 3), (450, 4), (540, 5),
    (630, 6), (720, 7), (810, 8), (900, 9), (math.inf, 10),
)
FIBER_POINTS: tuple[tuple[float, int], ...] = (
    (0.9, 0), (1.9, 1), (2.8, 2), (3.7, 3), (4.7, 4), (math.inf, 5),
)
PROTEIN_POINTS: tuple[tuple[float, int], ...] = (
    (1.6, 0), (3.2, 1), (4.8, 2), (6.4, 3), (8, 4), (math.inf, 5),
)


def _points_for(value: float, table: tuple[tuple[float, int], ...]) -> int:
    """Return the point value for a non-negative value using upper bounds."""
    for upper_bound, points in table:
        if value <= upper_bound:
            return points
    raise AssertionError("Point table must end with an infinite upper bound.")


class NutriScoreCalculator:
    """Calculate the original Nutri-Score for normalized, general food data.

    The supported input is the complete Stage-3 JSON document or its
    ``normalized`` member.  Only a ``per_100g`` basis is scored, because this
    baseline does not infer food categories and therefore cannot apply the
    original algorithm's beverage or other category-specific rules.
    """

    REQUIRED_FIELDS = {
        "calories_kcal": "energy",
        "total_sugars_g": "sugars",
        "saturated_fat_g": "saturated_fat",
        "sodium_mg": "sodium",
        "fiber_g": "fiber",
        "protein_g": "protein",
    }

    def calculate(self, stage3_data: Mapping[str, Any]) -> dict[str, Any]:
        """Return a complete, auditable score breakdown.

        Missing or invalid mandatory nutrients produce component-level details
        but no final score or grade.  FVLN is always declared unavailable in
        this baseline: it contributes zero points for calculation, but makes
        the result explicitly partial rather than claiming a 0% FVLN content.
        """
        normalized = self._normalized_section(stage3_data)
        nutrition = normalized.get("nutrition")
        basis = normalized.get("basis")
        warnings: list[str] = [
            "FVLN percentage unavailable; deterministic score is based on partial input.",
            "Only the original general-food Nutri-Score convention is implemented; special-category rules are unsupported.",
        ]

        supported_basis = (
            isinstance(basis, Mapping)
            and basis.get("type") == "per_100g"
            and normalized.get("normalization_possible") is True
        )
        if not supported_basis:
            warnings.append(
                "A normalized per_100g basis is required for the supported general-food calculation."
            )
        if not isinstance(nutrition, Mapping):
            nutrition = {}
            warnings.append("Stage 3 normalized nutrition data is missing or invalid.")

        energy_kcal = self._numeric_value(nutrition.get("calories_kcal"))
        energy_kj = energy_kcal * KCAL_TO_KJ if energy_kcal is not None else None

        negative_points = {
            "energy": self._component(
                energy_kj,
                "kJ",
                ENERGY_POINTS,
                source_value=energy_kcal,
                source_unit="kcal",
                display_value=round(energy_kj, 4) if energy_kj is not None else None,
            ),
            "sugars": self._component(self._numeric_value(nutrition.get("total_sugars_g")), "g", SUGAR_POINTS),
            "saturated_fat": self._component(
                self._numeric_value(nutrition.get("saturated_fat_g")), "g", SATURATED_FAT_POINTS
            ),
            "sodium": self._component(self._numeric_value(nutrition.get("sodium_mg")), "mg", SODIUM_POINTS),
        }
        positive_points = {
            "fiber": self._component(self._numeric_value(nutrition.get("fiber_g")), "g", FIBER_POINTS),
            "protein": self._component(self._numeric_value(nutrition.get("protein_g")), "g", PROTEIN_POINTS),
            "fruit_vegetable_legume_nut": {
                "available": False,
                "points": 0,
                "reason": "FVLN percentage unavailable from extracted nutrition data",
            },
        }

        missing_components = [
            name for name, component in {**negative_points, "fiber": positive_points["fiber"], "protein": positive_points["protein"]}.items()
            if component["points"] is None
        ]
        if missing_components:
            warnings.append(
                "Required nutrient values are missing or invalid: " + ", ".join(missing_components) + "."
            )

        score_available = supported_basis and not missing_components
        if score_available:
            negative_total = sum(component["points"] for component in negative_points.values())
            protein_included = not (
                negative_total >= 11
                and positive_points["fruit_vegetable_legume_nut"]["points"] < 5
            )
            positive_points["protein"]["included_in_final_score"] = protein_included
            positive_total = (
                positive_points["fiber"]["points"]
                + positive_points["fruit_vegetable_legume_nut"]["points"]
                + (positive_points["protein"]["points"] if protein_included else 0)
            )
            final_score = negative_total - positive_total
            grade = self._grade_for(final_score)
            if not protein_included:
                warnings.append(
                    "Protein points were excluded because negative points are at least 11 and FVLN points are below 5."
                )
        else:
            negative_total = None
            positive_total = None
            positive_points["protein"]["included_in_final_score"] = False
            final_score = None
            grade = None

        negative_points["total"] = negative_total
        positive_points["total"] = positive_total
        return {
            "algorithm": "Original Nutri-Score (general food baseline)",
            "algorithm_version": "pre-2023",
            "calculation_complete": False,
            "score_available": score_available,
            "category": "general_food",
            "negative_points": negative_points,
            "positive_points": positive_points,
            "final_score": final_score,
            "grade": grade,
            "warnings": warnings,
        }

    @staticmethod
    def _normalized_section(stage3_data: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(stage3_data, Mapping):
            return {}
        normalized = stage3_data.get("normalized")
        return normalized if isinstance(normalized, Mapping) else stage3_data

    @staticmethod
    def _numeric_value(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None

    @staticmethod
    def _component(
        value: float | None,
        unit: str,
        table: tuple[tuple[float, int], ...],
        *,
        source_value: float | None = None,
        source_unit: str | None = None,
        display_value: float | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "input_value": value if display_value is None else display_value,
            "unit": unit,
            "points": _points_for(value, table) if value is not None else None,
        }
        if source_unit is not None:
            result["source_input_value"] = source_value
            result["source_unit"] = source_unit
            result["conversion"] = "kcal × 4.184 = kJ"
        if value is None:
            result["reason"] = "Required nutrient value is missing or invalid"
        return result

    @staticmethod
    def _grade_for(score: int) -> str:
        if score <= -1:
            return "A"
        if score <= 2:
            return "B"
        if score <= 10:
            return "C"
        if score <= 18:
            return "D"
        return "E"
