"""
Stage 3 tests — NutritionNormalizer
====================================

Run with:

    cd C:\\Users\\Sai\\OneDrive\\Desktop\\ADL\\nutriParse
    nutriparse-env\\Scripts\\python -m pytest src\\tests\\test_normalizer.py -v

No external dependencies beyond Python's standard library and pytest.
"""

import sys
import os

# Ensure src/ is on the path when running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nutrition_normalizer import NutritionNormalizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_input(
    *,
    serving_amount=35,
    serving_unit="g",
    calories=140,
    total_fat_g=3,
    saturated_fat_g=0,
    trans_fat_g=0,
    cholesterol_mg=0,
    sodium_mg=0,
    carbohydrate_g=23,
    fiber_g=4,
    total_sugars_g=5,
    added_sugars_g=0,
    protein_g=4,
    vitamin_d_mcg=0,
    calcium_mg=14,
    iron_mg=1,
    potassium_mg=195,
) -> dict:
    """Build a minimal Stage-2 nutrition dict for testing."""
    return {
        "serving_size": {"amount": serving_amount, "unit": serving_unit},
        "nutrition": {
            "calories":        calories,
            "total_fat_g":     total_fat_g,
            "saturated_fat_g": saturated_fat_g,
            "trans_fat_g":     trans_fat_g,
            "cholesterol_mg":  cholesterol_mg,
            "sodium_mg":       sodium_mg,
            "carbohydrate_g":  carbohydrate_g,
            "fiber_g":         fiber_g,
            "total_sugars_g":  total_sugars_g,
            "added_sugars_g":  added_sugars_g,
            "protein_g":       protein_g,
            "vitamin_d_mcg":   vitamin_d_mcg,
            "calcium_mg":      calcium_mg,
            "iron_mg":         iron_mg,
            "potassium_mg":    potassium_mg,
        },
    }


SCALE_35 = 100.0 / 35   # ≈ 2.857142857


def approx(value, tol=1e-6):
    """Return a pytest.approx with absolute tolerance."""
    return pytest.approx(value, abs=tol)


# ---------------------------------------------------------------------------
# TEST 1 — 35 g serving → calories normalized to 100 g
# ---------------------------------------------------------------------------

class TestCaloriesNormalization:
    def test_calories_scaled_correctly(self):
        data   = make_input(serving_amount=35, calories=140)
        result = NutritionNormalizer().normalize(data)

        expected = 140 * SCALE_35  # ≈ 400.0
        assert result.normalized_nutrition["calories_kcal"] == approx(expected)

    def test_basis_type_is_per_100g(self):
        result = NutritionNormalizer().normalize(make_input())
        assert result.basis["type"] == "per_100g"
        assert result.basis["unit"] == "g"
        assert result.basis["amount"] == 100


# ---------------------------------------------------------------------------
# TEST 2 — 3 g fat per 35 g → correct per-100 g value
# ---------------------------------------------------------------------------

class TestFatNormalization:
    def test_total_fat_scaled_correctly(self):
        data   = make_input(serving_amount=35, total_fat_g=3)
        result = NutritionNormalizer().normalize(data)

        expected = 3 * SCALE_35  # ≈ 8.5714…
        assert result.normalized_nutrition["total_fat_g"] == approx(expected)

    def test_scale_factor_is_100_over_serving(self):
        # 50 g serving
        data   = make_input(serving_amount=50, total_fat_g=10)
        result = NutritionNormalizer().normalize(data)

        expected = 10 * (100.0 / 50)  # 20.0
        assert result.normalized_nutrition["total_fat_g"] == approx(expected)


# ---------------------------------------------------------------------------
# TEST 3 — zero values remain zero
# ---------------------------------------------------------------------------

class TestZeroPreservation:
    def test_sodium_zero_stays_zero(self):
        data   = make_input(sodium_mg=0)
        result = NutritionNormalizer().normalize(data)

        assert result.normalized_nutrition["sodium_mg"] == 0

    def test_trans_fat_zero_stays_zero(self):
        data   = make_input(trans_fat_g=0)
        result = NutritionNormalizer().normalize(data)

        assert result.normalized_nutrition["trans_fat_g"] == 0


# ---------------------------------------------------------------------------
# TEST 4 — missing values (None) remain None, never become 0
# ---------------------------------------------------------------------------

class TestMissingValuePreservation:
    def test_null_fiber_stays_null_in_normalized(self):
        data = make_input()
        data["nutrition"]["fiber_g"] = None
        result = NutritionNormalizer().normalize(data)

        assert result.normalized_nutrition["fiber_g"] is None

    def test_null_vitamin_d_stays_null(self):
        data = make_input()
        data["nutrition"]["vitamin_d_mcg"] = None
        result = NutritionNormalizer().normalize(data)

        assert result.normalized_nutrition["vitamin_d_mcg"] is None

    def test_null_differs_from_zero(self):
        """Explicitly assert that null and 0 are treated differently."""
        data_null = make_input()
        data_null["nutrition"]["iron_mg"] = None
        result_null = NutritionNormalizer().normalize(data_null)

        data_zero = make_input(iron_mg=0)
        result_zero = NutritionNormalizer().normalize(data_zero)

        assert result_null.normalized_nutrition["iron_mg"] is None
        assert result_zero.normalized_nutrition["iron_mg"] == 0
        # The two must NOT be equal
        assert result_null.normalized_nutrition["iron_mg"] != result_zero.normalized_nutrition["iron_mg"]


# ---------------------------------------------------------------------------
# TEST 5 — per-100 g input is not double-normalized
# ---------------------------------------------------------------------------

class TestNoDoubleNormalization:
    def test_100g_serving_scale_factor_is_1(self):
        """If the label already reports per 100 g, the scale factor is 1."""
        data   = make_input(serving_amount=100, calories=400)
        result = NutritionNormalizer().normalize(data)

        # 400 × (100/100) = 400 — unchanged
        assert result.normalized_nutrition["calories_kcal"] == approx(400.0)

    def test_100g_total_fat_unchanged(self):
        data   = make_input(serving_amount=100, total_fat_g=8.57)
        result = NutritionNormalizer().normalize(data)

        assert result.normalized_nutrition["total_fat_g"] == approx(8.57)


# ---------------------------------------------------------------------------
# TEST 6 — negative values produce ERROR-level issues
# ---------------------------------------------------------------------------

class TestNegativeValueValidation:
    def test_negative_calories_produces_error(self):
        data = make_input(calories=-10)
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "NEGATIVE_VALUE" in codes
        assert result.is_valid() is False

    def test_negative_sodium_produces_error(self):
        data = make_input(sodium_mg=-5)
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "NEGATIVE_VALUE" in codes

    def test_valid_data_no_errors(self):
        result = NutritionNormalizer().normalize(make_input())
        assert result.is_valid() is True


# ---------------------------------------------------------------------------
# TEST 7 — saturated fat > total fat produces WARNING
# ---------------------------------------------------------------------------

class TestSaturatedFatConsistency:
    def test_saturated_exceeds_total_warning(self):
        data = make_input(total_fat_g=3, saturated_fat_g=5)
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "CROSS_FIELD_INCONSISTENCY" in codes

        # Must be a warning, not an error
        for issue in result.issues:
            if issue.code == "CROSS_FIELD_INCONSISTENCY":
                assert issue.level == "warning"

    def test_saturated_equals_total_is_fine(self):
        data = make_input(total_fat_g=3, saturated_fat_g=3)
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "CROSS_FIELD_INCONSISTENCY" not in codes


# ---------------------------------------------------------------------------
# TEST 8 — added sugars > total sugars produces WARNING
# ---------------------------------------------------------------------------

class TestAddedSugarsConsistency:
    def test_added_exceeds_total_warning(self):
        data = make_input(total_sugars_g=5, added_sugars_g=8)
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "CROSS_FIELD_INCONSISTENCY" in codes

    def test_added_equals_total_is_fine(self):
        data = make_input(total_sugars_g=5, added_sugars_g=5)
        result = NutritionNormalizer().normalize(data)

        # Should NOT produce a cross-field inconsistency for this pair
        for issue in result.issues:
            if issue.code == "CROSS_FIELD_INCONSISTENCY" and issue.field == "added_sugars":
                pytest.fail("Unexpected CROSS_FIELD_INCONSISTENCY for added_sugars == total_sugars")


# ---------------------------------------------------------------------------
# TEST 9 — unrecognized serving unit produces ERROR
# ---------------------------------------------------------------------------

class TestUnrecognizedUnit:
    def test_oz_serving_produces_error(self):
        data = make_input()
        data["serving_size"]["unit"] = "oz"
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "SERVING_UNIT_UNRECOGNIZED" in codes
        assert result.normalization_possible is False

    def test_normalized_values_null_when_unit_unrecognized(self):
        data = make_input()
        data["serving_size"]["unit"] = "oz"
        result = NutritionNormalizer().normalize(data)

        # All normalized values must be None when basis is unknown
        for v in result.normalized_nutrition.values():
            assert v is None


# ---------------------------------------------------------------------------
# TEST 10 — volume-based serving recognized correctly
# ---------------------------------------------------------------------------

class TestVolumeServing:
    def test_ml_serving_basis_is_per_100ml(self):
        data = make_input(serving_amount=250, serving_unit="ml", calories=50)
        result = NutritionNormalizer().normalize(data)

        assert result.basis["type"] == "per_100ml"
        assert result.basis["unit"] == "ml"

    def test_ml_serving_calories_scaled(self):
        data = make_input(serving_amount=250, serving_unit="ml", calories=50)
        result = NutritionNormalizer().normalize(data)

        expected = 50 * (100.0 / 250)   # 20.0
        assert result.normalized_nutrition["calories_kcal"] == approx(expected)


# ---------------------------------------------------------------------------
# TEST 11 — normalization does not mutate original data
# ---------------------------------------------------------------------------

class TestNonMutation:
    def test_original_nutrition_not_modified(self):
        data   = make_input(serving_amount=35, calories=140)
        before = dict(data["nutrition"])

        NutritionNormalizer().normalize(data)

        assert data["nutrition"] == before

    def test_original_serving_size_not_modified(self):
        data   = make_input()
        before = dict(data["serving_size"])

        NutritionNormalizer().normalize(data)

        assert data["serving_size"] == before


# ---------------------------------------------------------------------------
# TEST 12 — repeated normalization produces identical results
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_result_on_repeated_calls(self):
        data    = make_input()
        norm    = NutritionNormalizer()
        result1 = norm.normalize(data)
        result2 = norm.normalize(data)

        assert result1.normalized_nutrition == result2.normalized_nutrition
        assert len(result1.issues) == len(result2.issues)

    def test_different_normalizer_instances_give_same_result(self):
        data    = make_input()
        result1 = NutritionNormalizer().normalize(data)
        result2 = NutritionNormalizer().normalize(data)

        assert result1.normalized_nutrition == result2.normalized_nutrition


# ---------------------------------------------------------------------------
# TEST 13 — missing serving size produces warning and null normalized values
# ---------------------------------------------------------------------------

class TestMissingServingSize:
    def test_missing_amount_warns(self):
        data = make_input()
        data["serving_size"]["amount"] = None
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "SERVING_SIZE_MISSING" in codes
        assert result.normalization_possible is False

    def test_missing_unit_warns(self):
        data = make_input()
        data["serving_size"]["unit"] = None
        result = NutritionNormalizer().normalize(data)

        codes = [i.code for i in result.issues]
        assert "SERVING_SIZE_MISSING" in codes

    def test_all_normalized_null_when_serving_missing(self):
        data = make_input()
        data["serving_size"]["amount"] = None
        result = NutritionNormalizer().normalize(data)

        for v in result.normalized_nutrition.values():
            assert v is None


# ---------------------------------------------------------------------------
# TEST 14 — to_dict() structure is correct
# ---------------------------------------------------------------------------

class TestToDictStructure:
    def test_output_has_required_keys(self):
        result = NutritionNormalizer().normalize(make_input())
        output = result.to_dict(input_image="input/food_label.jpg")

        assert "source" in output
        assert "original" in output
        assert "normalized" in output
        assert "validation" in output

    def test_original_basis_is_per_serving(self):
        result = NutritionNormalizer().normalize(make_input())
        output = result.to_dict()

        assert output["original"]["basis"]["type"] == "per_serving"

    def test_validation_contains_valid_flag(self):
        result = NutritionNormalizer().normalize(make_input())
        output = result.to_dict()

        assert "valid" in output["validation"]
        assert output["validation"]["valid"] is True


# ---------------------------------------------------------------------------
# TEST 15 — full test-image scenario (verifies expected values)
# ---------------------------------------------------------------------------

class TestCurrentTestImage:
    """
    End-to-end check against the known test image values.
    Values are NOT hardcoded into the normalizer; they are computed here
    using the same formula so we can verify the normalizer is correct.
    """

    def setup_method(self):
        self.data = make_input(
            serving_amount=35,
            calories=140,
            total_fat_g=3,
            saturated_fat_g=0,
            trans_fat_g=0,
            cholesterol_mg=0,
            sodium_mg=0,
            carbohydrate_g=23,
            fiber_g=4,
            total_sugars_g=5,
            added_sugars_g=0,
            protein_g=4,
            vitamin_d_mcg=0,
            calcium_mg=14,
            iron_mg=1,
            potassium_mg=195,
        )
        self.result = NutritionNormalizer().normalize(self.data)
        self.n = self.result.normalized_nutrition
        self.s = 100.0 / 35

    def test_calories(self):
        assert self.n["calories_kcal"] == approx(140 * self.s)

    def test_total_fat(self):
        assert self.n["total_fat_g"] == approx(3 * self.s)

    def test_carbohydrate(self):
        assert self.n["carbohydrate_g"] == approx(23 * self.s)

    def test_protein(self):
        assert self.n["protein_g"] == approx(4 * self.s)

    def test_potassium(self):
        assert self.n["potassium_mg"] == approx(195 * self.s)

    def test_zero_sodium_stays_zero(self):
        assert self.n["sodium_mg"] == 0

    def test_no_errors(self):
        assert self.result.is_valid() is True
