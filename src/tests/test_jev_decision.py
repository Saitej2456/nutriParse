from __future__ import annotations

from src.jev_decision import OpenJevDecisionLayer


class FakeChoice:
    def __init__(self, *, instructions, criteria):
        self.instructions = instructions
        self.criteria = criteria


class FakeEngine:
    def __init__(self, response):
        self.response = response
        self.state = None
        self.questions = None

    def system_one(self, state, questions):
        self.state = state
        self.questions = questions
        return self.response


def normalized_output(*, errors=None, warnings=None, nutrition_overrides=None):
    nutrition = {
        "calories_kcal": 300,
        "total_sugars_g": 4,
        "saturated_fat_g": 1,
        "sodium_mg": 90,
        "fiber_g": 3,
        "protein_g": 5,
    }
    nutrition.update(nutrition_overrides or {})
    return {
        "normalized": {"nutrition": nutrition},
        "validation": {"errors": errors or [], "warnings": warnings or []},
    }


def nutri_score(*, grade="B", score_available=True):
    return {
        "grade": grade,
        "final_score": 1,
        "score_available": score_available,
        "calculation_complete": False,
        "warnings": [
            "FVLN percentage unavailable; deterministic score is based on partial input.",
            "Only the original general-food Nutri-Score convention is implemented; special-category rules are unsupported.",
        ],
    }


def response_for(decision):
    probabilities = {
        "TRUST": 0.96 if decision == "TRUST" else 0.02,
        "REVIEW": 0.96 if decision == "REVIEW" else 0.02,
        "REJECT": 0.96 if decision == "REJECT" else 0.02,
    }
    return {
        "answers": {
            "reliability_decision": {
                "type": "choice",
                "choice": decision,
                "confidence": 0.94,
                "probabilities": probabilities,
            }
        }
    }


def layer_with(response):
    engine = FakeEngine(response)
    return (
        OpenJevDecisionLayer(
            engine_factory=lambda: engine,
            choice_factory=FakeChoice,
        ),
        engine,
    )


def test_clean_result_maps_mocked_openjev_trust_response():
    layer, engine = layer_with(response_for("TRUST"))
    result = layer.decide(normalized_output(), nutri_score())

    assert result["status"] == "success"
    assert result["decision"] == "TRUST"
    assert result["confidence"] == 0.94
    assert result["input_summary"]["missing_required_fields"] == []
    assert result["input_summary"]["extraction_quality"] == {"available": False, "value": None}
    assert set(engine.questions["reliability_decision"].criteria) == {"TRUST", "REVIEW", "REJECT"}
    assert engine.state == {
        "deterministic_grade": "B",
        "score_available": True,
        "normalization_validation": {"errors": [], "warnings": []},
        "missing_required_nutrition_fields": [],
        "extraction_quality": {"available": False, "value": None},
    }
    state_text = str(engine.state)
    assert "calculation_complete" not in state_text
    assert "FVLN percentage unavailable" not in state_text
    assert "special-category rules" not in state_text


def test_warning_result_passes_factual_warning_to_mocked_openjev_review_response():
    warning = {"message": "Fiber (8) exceeds Total carbohydrate (4)."}
    layer, engine = layer_with(response_for("REVIEW"))
    result = layer.decide(normalized_output(warnings=[warning]), nutri_score())

    assert result["status"] == "success"
    assert result["decision"] == "REVIEW"
    assert result["input_summary"]["validation_warnings"] == [warning["message"]]
    assert engine.state["normalization_validation"]["warnings"] == [warning["message"]]


def test_severe_invalid_or_incomplete_result_maps_mocked_openjev_reject_response():
    error = {"message": "'sodium_mg' has negative value: -1."}
    layer, engine = layer_with(response_for("REJECT"))
    result = layer.decide(
        normalized_output(errors=[error], nutrition_overrides={"sodium_mg": None}),
        nutri_score(grade=None),
    )

    assert result["status"] == "success"
    assert result["decision"] == "REJECT"
    assert result["input_summary"]["validation_errors"] == [error["message"]]
    assert result["input_summary"]["missing_required_fields"] == ["sodium_mg"]
    assert engine.state["normalization_validation"]["errors"] == [error["message"]]
    assert engine.state["missing_required_nutrition_fields"] == ["sodium_mg"]


def test_openjev_failure_is_explicit_and_does_not_replace_stage4_result():
    def unavailable_engine():
        raise ConnectionError("Ollama is not running")

    deterministic = nutri_score(grade="A")
    layer = OpenJevDecisionLayer(engine_factory=unavailable_engine, choice_factory=FakeChoice)
    result = layer.decide(normalized_output(), deterministic)

    assert result["status"] == "unavailable"
    assert result["decision"] is None
    assert result["confidence"] is None
    assert result["probabilities"] is None
    assert "ConnectionError" in result["error"]
    assert deterministic["grade"] == "A"
