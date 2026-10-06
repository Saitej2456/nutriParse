"""
Stage 3: Nutrition Normalization and Validation
================================================

NutritionNormalizer takes the canonical nutrition dict produced by
NutritionParser (Stage 2) and returns a fully-normalized, validated
representation suitable for downstream grading (Stage 4+).

Responsibilities
----------------
1. Unit normalization  — ensure all nutrients use their canonical units.
2. Basis normalization — convert per-serving values to per-100 g or per-100 ml.
3. Missing-value handling — preserve null for absent fields; never coerce to 0.
4. Sanity validation   — flag negative values, impossible numbers, etc.
5. Cross-field consistency — flag relationships that violate physical constraints.
6. Optional energy check — warn when macronutrient energy deviates from calories.

Design rules
------------
- Deterministic: given the same input, always produce the same output.
- Non-destructive: original extracted values are preserved in the output.
- Explicit: nothing is assumed; every decision is recorded.
- Fail-safe: missing data is surfaced as warnings, not silently corrected.

No grading logic of any kind lives here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Canonical nutrient schema
# ---------------------------------------------------------------------------
# Every nutrient has a canonical name, its expected unit in Stage-2 output,
# and its canonical unit for the normalized representation.
# These must stay in sync with NutritionParser field names.

NUTRIENT_SCHEMA: list[dict] = [
    # name                 stage2_key           canonical_unit
    {"name": "calories",       "key": "calories",        "unit": "kcal"},
    {"name": "total_fat",      "key": "total_fat_g",     "unit": "g"},
    {"name": "saturated_fat",  "key": "saturated_fat_g", "unit": "g"},
    {"name": "trans_fat",      "key": "trans_fat_g",     "unit": "g"},
    {"name": "cholesterol",    "key": "cholesterol_mg",  "unit": "mg"},
    {"name": "sodium",         "key": "sodium_mg",       "unit": "mg"},
    {"name": "carbohydrate",   "key": "carbohydrate_g",  "unit": "g"},
    {"name": "fiber",          "key": "fiber_g",         "unit": "g"},
    {"name": "total_sugars",   "key": "total_sugars_g",  "unit": "g"},
    {"name": "added_sugars",   "key": "added_sugars_g",  "unit": "g"},
    {"name": "protein",        "key": "protein_g",       "unit": "g"},
    {"name": "vitamin_d",      "key": "vitamin_d_mcg",   "unit": "mcg"},
    {"name": "calcium",        "key": "calcium_mg",      "unit": "mg"},
    {"name": "iron",           "key": "iron_mg",         "unit": "mg"},
    {"name": "potassium",      "key": "potassium_mg",    "unit": "mg"},
]

# Normalized output keys (unit suffix is part of the key name)
NORMALIZED_KEY_MAP = {
    "calories":      "calories_kcal",
    "total_fat":     "total_fat_g",
    "saturated_fat": "saturated_fat_g",
    "trans_fat":     "trans_fat_g",
    "cholesterol":   "cholesterol_mg",
    "sodium":        "sodium_mg",
    "carbohydrate":  "carbohydrate_g",
    "fiber":         "fiber_g",
    "total_sugars":  "total_sugars_g",
    "added_sugars":  "added_sugars_g",
    "protein":       "protein_g",
    "vitamin_d":     "vitamin_d_mcg",
    "calcium":       "calcium_mg",
    "iron":          "iron_mg",
    "potassium":     "potassium_mg",
}

# Accepted serving-size units and the basis they imply
MASS_UNITS   = {"g", "gram", "grams"}
VOLUME_UNITS = {"ml", "milliliter", "milliliters", "millilitre", "millilitres"}

# Macronutrient energy densities (kcal per gram) — used for optional check
ENERGY_DENSITY = {
    "protein_g":     4.0,
    "carbohydrate_g": 4.0,
    "total_fat_g":   9.0,
}

# Tolerance for energy consistency check (fraction of stated calories)
ENERGY_TOLERANCE = 0.20   # ±20 %

# Decimal places for normalized values in the final JSON
NORMALIZED_PRECISION = 4


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation warning or error."""

    level: str           # "warning" or "error"
    code: str            # machine-readable identifier
    message: str         # human-readable description
    field: Optional[str] = None   # nutrient name, if applicable


@dataclass
class NormalizationResult:
    """
    Complete output of Stage 3.

    Attributes
    ----------
    original_nutrition:
        The nutrition dict exactly as produced by Stage 2 (per-serving).
    original_serving_size:
        The serving size dict from Stage 2.
    basis:
        The normalized basis descriptor.
    normalized_nutrition:
        Nutrient values scaled to the normalized basis.
        null values remain null (missing ≠ zero).
    issues:
        Validation warnings and errors.
    normalization_possible:
        False when the basis cannot be determined (e.g., serving size missing).
    """

    original_nutrition: dict
    original_serving_size: dict
    basis: dict
    normalized_nutrition: dict
    issues: list[ValidationIssue] = field(default_factory=list)
    normalization_possible: bool = True

    def is_valid(self) -> bool:
        """True if there are no ERROR-level issues."""
        return all(i.level != "error" for i in self.issues)

    def to_dict(self, *, input_image: Optional[str] = None) -> dict:
        """
        Serialize to the canonical output structure.

        Precision: normalized numeric values are rounded to
        NORMALIZED_PRECISION decimal places for readability.
        The full-precision floats are used internally.
        """

        def _round(v):
            if v is None:
                return None
            if isinstance(v, float) and v == int(v):
                return int(v)
            if isinstance(v, float):
                rounded = round(v, NORMALIZED_PRECISION)
                # Remove trailing decimal zeros where the value is whole
                if rounded == int(rounded):
                    return int(rounded)
                return rounded
            return v

        rounded_norm = {k: _round(v) for k, v in self.normalized_nutrition.items()}

        result = {}

        if input_image is not None:
            result["source"] = {"input_image": input_image}

        result["original"] = {
            "serving_size": self.original_serving_size,
            "basis": {"type": "per_serving"},
            "nutrition": self.original_nutrition,
        }

        result["normalized"] = {
            "basis": self.basis,
            "normalization_possible": self.normalization_possible,
            "nutrition": rounded_norm,
        }

        result["validation"] = {
            "valid": self.is_valid(),
            "warnings": [
                {
                    "level": i.level,
                    "code": i.code,
                    "field": i.field,
                    "message": i.message,
                }
                for i in self.issues
                if i.level == "warning"
            ],
            "errors": [
                {
                    "level": i.level,
                    "code": i.code,
                    "field": i.field,
                    "message": i.message,
                }
                for i in self.issues
                if i.level == "error"
            ],
        }

        return result


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

class NutritionNormalizer:
    """
    Stage 3: Normalize and validate a canonical nutrition dict.

    Usage
    -----
    normalizer = NutritionNormalizer()
    result = normalizer.normalize(nutrition_data)
    output = result.to_dict(input_image="input/food_label.jpg")

    Parameters
    ----------
    check_energy_consistency:
        When True, an optional macronutrient energy cross-check is performed.
        Deviations beyond ENERGY_TOLERANCE produce a warning, not an error.
    """

    def __init__(self, *, check_energy_consistency: bool = True):
        self.check_energy_consistency = check_energy_consistency

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def normalize(self, nutrition_data: dict) -> NormalizationResult:
        """
        Normalize and validate a Stage-2 nutrition dict.

        Parameters
        ----------
        nutrition_data:
            Dict as returned by NutritionParser.parse(), containing:
                {
                    "serving_size": {"amount": ..., "unit": ...},
                    "nutrition":    { ... field: value ... }
                }

        Returns
        -------
        NormalizationResult
        """

        issues: list[ValidationIssue] = []

        # Deep-copy originals so we never mutate the caller's data
        original_nutrition   = dict(nutrition_data.get("nutrition", {}))
        original_serving_size = dict(nutrition_data.get("serving_size", {}))

        # -----------------------------------------------------------------
        # Step 1: Determine normalized basis
        # -----------------------------------------------------------------
        serving_amount, serving_unit, basis, scale_factor = self._determine_basis(
            original_serving_size, issues
        )

        normalization_possible = scale_factor is not None

        # -----------------------------------------------------------------
        # Step 2: Validate original (per-serving) values
        # -----------------------------------------------------------------
        self._validate_original(original_nutrition, issues)

        # -----------------------------------------------------------------
        # Step 3: Build normalized nutrition dict
        # -----------------------------------------------------------------
        normalized_nutrition = self._build_normalized(
            original_nutrition, scale_factor, issues
        )

        # -----------------------------------------------------------------
        # Step 4: Cross-field consistency on ORIGINAL values
        # -----------------------------------------------------------------
        self._check_cross_field(original_nutrition, issues)

        # -----------------------------------------------------------------
        # Step 5: Optional energy consistency check (on original values)
        # -----------------------------------------------------------------
        if self.check_energy_consistency:
            self._check_energy(original_nutrition, issues)

        return NormalizationResult(
            original_nutrition=original_nutrition,
            original_serving_size=original_serving_size,
            basis=basis,
            normalized_nutrition=normalized_nutrition,
            issues=issues,
            normalization_possible=normalization_possible,
        )

    # ------------------------------------------------------------------
    # Step 1: Determine normalized basis
    # ------------------------------------------------------------------

    def _determine_basis(
        self,
        serving_size: dict,
        issues: list[ValidationIssue],
    ) -> tuple[Optional[float], Optional[str], dict, Optional[float]]:
        """
        Determine the scale factor to convert per-serving values to
        the target normalized basis (per 100 g or per 100 ml).

        Returns (serving_amount, serving_unit, basis_dict, scale_factor).
        scale_factor is None when normalization is impossible.
        """

        amount = serving_size.get("amount")
        unit   = serving_size.get("unit")

        # --- Missing serving size ---
        if amount is None or unit is None:
            issues.append(ValidationIssue(
                level="warning",
                code="SERVING_SIZE_MISSING",
                message=(
                    "Serving size is missing. "
                    "Cannot normalize to a per-100 basis. "
                    "Normalized values will be null."
                ),
            ))
            return None, None, {"type": "unknown", "reason": "serving_size_missing"}, None

        # --- Non-positive serving size ---
        if amount <= 0:
            issues.append(ValidationIssue(
                level="error",
                code="SERVING_SIZE_NONPOSITIVE",
                message=f"Serving size amount must be positive, got {amount}.",
                field="serving_size",
            ))
            return amount, unit, {"type": "unknown", "reason": "serving_size_nonpositive"}, None

        unit_lower = str(unit).lower().strip()

        if unit_lower in MASS_UNITS:
            basis = {
                "type": "per_100g",
                "amount": 100,
                "unit": "g",
                "description": (
                    f"Values normalized from {amount} g serving to 100 g basis. "
                    f"Scale factor = 100 / {amount} = {100 / amount:.6f}."
                ),
            }
            scale_factor = 100.0 / amount
            return amount, unit, basis, scale_factor

        if unit_lower in VOLUME_UNITS:
            basis = {
                "type": "per_100ml",
                "amount": 100,
                "unit": "ml",
                "description": (
                    f"Values normalized from {amount} ml serving to 100 ml basis. "
                    f"Scale factor = 100 / {amount} = {100 / amount:.6f}."
                ),
            }
            scale_factor = 100.0 / amount
            return amount, unit, basis, scale_factor

        # --- Unrecognized unit ---
        issues.append(ValidationIssue(
            level="error",
            code="SERVING_UNIT_UNRECOGNIZED",
            message=(
                f"Serving size unit '{unit}' is not recognized. "
                f"Expected a mass unit {sorted(MASS_UNITS)} "
                f"or volume unit {sorted(VOLUME_UNITS)}."
            ),
            field="serving_size",
        ))
        return amount, unit, {"type": "unknown", "reason": f"unrecognized_unit:{unit}"}, None

    # ------------------------------------------------------------------
    # Step 2: Validate original per-serving values
    # ------------------------------------------------------------------

    def _validate_original(
        self,
        nutrition: dict,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Validate individual nutrient values.

        Rules
        -----
        - Negative values produce an error.
        - Non-finite values (NaN, Inf) produce an error.
        - null (None) values are allowed and preserved.
        """

        for spec in NUTRIENT_SCHEMA:
            key   = spec["key"]
            name  = spec["name"]
            value = nutrition.get(key)

            if value is None:
                # null is a valid representation of "not present on label"
                continue

            if not isinstance(value, (int, float)):
                issues.append(ValidationIssue(
                    level="error",
                    code="INVALID_TYPE",
                    message=f"'{key}' has non-numeric value: {value!r}.",
                    field=name,
                ))
                continue

            if not math.isfinite(value):
                issues.append(ValidationIssue(
                    level="error",
                    code="NON_FINITE_VALUE",
                    message=f"'{key}' has non-finite value: {value}.",
                    field=name,
                ))
                continue

            if value < 0:
                issues.append(ValidationIssue(
                    level="error",
                    code="NEGATIVE_VALUE",
                    message=f"'{key}' has negative value: {value}.",
                    field=name,
                ))

    # ------------------------------------------------------------------
    # Step 3: Build normalized nutrition dict
    # ------------------------------------------------------------------

    def _build_normalized(
        self,
        nutrition: dict,
        scale_factor: Optional[float],
        issues: list[ValidationIssue],
    ) -> dict:
        """
        Scale every nutrient by scale_factor.

        Rules
        -----
        - null stays null (missing ≠ zero).
        - If scale_factor is None, every value becomes null.
        - Negative values are preserved as-is (already flagged by validation).
        - Non-finite results produce an error and become null.
        """

        normalized: dict = {}

        for spec in NUTRIENT_SCHEMA:
            key      = spec["key"]
            name     = spec["name"]
            norm_key = NORMALIZED_KEY_MAP[spec["name"]]
            value    = nutrition.get(key)

            if value is None:
                normalized[norm_key] = None
                continue

            if scale_factor is None:
                normalized[norm_key] = None
                continue

            scaled = value * scale_factor

            if not math.isfinite(scaled):
                issues.append(ValidationIssue(
                    level="error",
                    code="NORMALIZED_NON_FINITE",
                    message=(
                        f"Normalized value for '{key}' is non-finite "
                        f"({value} × {scale_factor} = {scaled})."
                    ),
                    field=name,
                ))
                normalized[norm_key] = None
                continue

            normalized[norm_key] = scaled

        return normalized

    # ------------------------------------------------------------------
    # Step 4: Cross-field consistency
    # ------------------------------------------------------------------

    def _check_cross_field(
        self,
        nutrition: dict,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Check relationships between nutrient pairs.

        These produce WARNINGS (not errors) because some label layouts and
        rounding conventions may legitimately produce apparent inconsistencies.

        The original values are NEVER modified.
        """

        def _check_le(child_key, parent_key, child_name, parent_name):
            child  = nutrition.get(child_key)
            parent = nutrition.get(parent_key)
            if child is None or parent is None:
                return
            if child > parent:
                issues.append(ValidationIssue(
                    level="warning",
                    code="CROSS_FIELD_INCONSISTENCY",
                    message=(
                        f"{child_name} ({child}) exceeds {parent_name} ({parent}). "
                        "This may indicate a labeling inconsistency or OCR error."
                    ),
                    field=child_name.lower().replace(" ", "_"),
                ))

        _check_le("saturated_fat_g", "total_fat_g",    "Saturated fat", "Total fat")
        _check_le("trans_fat_g",     "total_fat_g",    "Trans fat",     "Total fat")
        _check_le("added_sugars_g",  "total_sugars_g", "Added sugars",  "Total sugars")
        _check_le("fiber_g",         "carbohydrate_g", "Fiber",         "Total carbohydrate")

    # ------------------------------------------------------------------
    # Step 5: Optional energy consistency check
    # ------------------------------------------------------------------

    def _check_energy(
        self,
        nutrition: dict,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Compare stated calories against macronutrient-derived energy.

        This is a WARNING-only check because rounding, fiber treatment,
        sugar alcohols, and label conventions can cause differences.

        Formula:
            estimated = 4 × protein_g + 4 × carbohydrate_g + 9 × fat_g

        Tolerance: ±ENERGY_TOLERANCE fraction of stated calories.
        """

        calories     = nutrition.get("calories")
        protein      = nutrition.get("protein_g")
        carbohydrate = nutrition.get("carbohydrate_g")
        fat          = nutrition.get("total_fat_g")

        if any(v is None for v in (calories, protein, carbohydrate, fat)):
            return   # skip check if any key macro is missing

        estimated = (
            ENERGY_DENSITY["protein_g"]      * protein +
            ENERGY_DENSITY["carbohydrate_g"] * carbohydrate +
            ENERGY_DENSITY["total_fat_g"]    * fat
        )

        if calories == 0:
            # Avoid division by zero; if all macros also give ~0 that's fine
            if abs(estimated) > 5:
                issues.append(ValidationIssue(
                    level="warning",
                    code="ENERGY_INCONSISTENCY",
                    message=(
                        f"Stated calories = 0, but macronutrient estimate = "
                        f"{estimated:.1f} kcal."
                    ),
                    field="calories",
                ))
            return

        deviation = abs(estimated - calories) / calories

        if deviation > ENERGY_TOLERANCE:
            issues.append(ValidationIssue(
                level="warning",
                code="ENERGY_INCONSISTENCY",
                message=(
                    f"Macronutrient energy estimate ({estimated:.1f} kcal) "
                    f"differs from stated calories ({calories} kcal) "
                    f"by {deviation * 100:.1f}% "
                    f"(tolerance = {ENERGY_TOLERANCE * 100:.0f}%). "
                    "This may be due to rounding, fiber treatment, "
                    "or labeling conventions."
                ),
                field="calories",
            ))
