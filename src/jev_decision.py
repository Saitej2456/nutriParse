"""Stage 5: OpenJev reliability decision for deterministic Nutri-Score output.

OpenJev is deliberately not asked to calculate nutrient points or a grade.
It receives the already-calculated deterministic result and reliability evidence,
then selects TRUST, REVIEW, or REJECT with model-derived probabilities.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

try:  # Supports both `python src/main.py` and package-style test imports.
    from .nutri_score import NutriScoreCalculator
except ImportError:  # pragma: no cover - exercised by the pipeline entry point
    from nutri_score import NutriScoreCalculator


OLLAMA_BACKEND = "ollama"
OLLAMA_MODEL = "qwen2.5-coder:14b"


class OpenJevDecisionLayer:
    """Make an OpenJev reliability decision from existing pipeline evidence.

    The OpenJev import and engine construction are intentionally deferred until
    ``decide`` is called.  A missing package, unavailable Ollama server, model
    failure, or malformed response therefore cannot stop the deterministic
    Nutri-Score pipeline.
    """

    def __init__(
        self,
        *,
        engine_factory: Callable[[], Any] | None = None,
        choice_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._engine_factory = engine_factory or self._make_ollama_engine
        self._choice_factory = choice_factory or self._make_choice

    def decide(
        self,
        normalized_output: Mapping[str, Any],
        nutri_score: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return a reliability decision or an explicit unavailable result."""
        input_summary = self.build_input_summary(normalized_output, nutri_score)
        state = self._build_state(input_summary)

        try:
            question = self._choice_factory(
                instructions=(
                    "Assess the reliability of the automated nutrition result "
                    "from the supplied evidence. Choose the most appropriate "
                    "decision without recalculating the Nutri-Score."
                ),
                criteria={
                    "TRUST": (
                        "The deterministic grade has sufficient supporting data "
                        "and no meaningful reliability concerns."
                    ),
                    "REVIEW": (
                        "The grade exists, but non-fatal warnings, inconsistencies, "
                        "or uncertainty warrant human review before acceptance."
                    ),
                    "REJECT": (
                        "The result is too incomplete, invalid, contradictory, or "
                        "unreliable to treat the automated grade as usable."
                    ),
                },
            )
            result = self._engine_factory().system_one(
                state,
                {"reliability_decision": question},
            )
            answer = result["answers"]["reliability_decision"]
            decision, confidence, probabilities = self._validated_answer(answer)
        except Exception as exc:  # The decision layer must never break Stage 4.
            return self._unavailable(input_summary, exc)

        return {
            "decision": decision,
            "confidence": confidence,
            "probabilities": probabilities,
            "backend": OLLAMA_BACKEND,
            "model": OLLAMA_MODEL,
            "input_summary": input_summary,
            "status": "success",
        }

    @staticmethod
    def build_input_summary(
        normalized_output: Mapping[str, Any],
        nutri_score: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Extract reliability evidence without changing Stage 3 or Stage 4."""
        validation = normalized_output.get("validation", {})
        normalized = normalized_output.get("normalized", {})
        nutrition = normalized.get("nutrition", {}) if isinstance(normalized, Mapping) else {}

        validation_errors = OpenJevDecisionLayer._issue_messages(
            validation.get("errors", []) if isinstance(validation, Mapping) else []
        )
        validation_warnings = OpenJevDecisionLayer._issue_messages(
            validation.get("warnings", []) if isinstance(validation, Mapping) else []
        )
        if not isinstance(nutrition, Mapping):
            nutrition = {}

        missing_required_fields = [
            field
            for field in NutriScoreCalculator.REQUIRED_FIELDS
            if nutrition.get(field) is None
        ]

        return {
            "deterministic_grade": nutri_score.get("grade"),
            "score_available": nutri_score.get("score_available"),
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "missing_required_fields": missing_required_fields,
            # PaddleOCR-VL output consumed by Stage 1 contains no stable,
            # pipeline-level extraction confidence value.  Do not invent one.
            "extraction_quality": {"available": False, "value": None},
        }

    @staticmethod
    def _issue_messages(issues: Any) -> list[str]:
        if not isinstance(issues, list):
            return []
        messages: list[str] = []
        for issue in issues:
            if isinstance(issue, Mapping):
                message = issue.get("message")
                messages.append(str(message) if message is not None else str(dict(issue)))
            else:
                messages.append(str(issue))
        return messages

    @staticmethod
    def _build_state(input_summary: Mapping[str, Any]) -> dict[str, Any]:
        """Provide only instance-specific reliability evidence to OpenJev.

        Stage 4 warnings and ``calculation_complete`` are intentionally absent:
        FVLN unavailability and special-category scope are baseline limitations,
        not evidence that this label's extraction or normalization is unreliable.
        """
        return {
            "deterministic_grade": input_summary["deterministic_grade"],
            "score_available": input_summary["score_available"],
            "normalization_validation": {
                "errors": input_summary["validation_errors"],
                "warnings": input_summary["validation_warnings"],
            },
            "missing_required_nutrition_fields": input_summary["missing_required_fields"],
            "extraction_quality": input_summary["extraction_quality"],
        }

    @staticmethod
    def _validated_answer(answer: Any) -> tuple[str, float, dict[str, float]]:
        """Validate real OpenJev response values rather than deriving them."""
        if not isinstance(answer, Mapping):
            raise ValueError("OpenJev reliability answer is not an object")
        decision = answer.get("choice")
        probabilities = answer.get("probabilities")
        confidence = answer.get("confidence")
        if decision not in {"TRUST", "REVIEW", "REJECT"}:
            raise ValueError("OpenJev returned an invalid reliability decision")
        if not isinstance(probabilities, Mapping):
            raise ValueError("OpenJev returned no probability mapping")
        clean_probabilities = {
            choice: float(probabilities[choice])
            for choice in ("TRUST", "REVIEW", "REJECT")
            if choice in probabilities
        }
        if set(clean_probabilities) != {"TRUST", "REVIEW", "REJECT"}:
            raise ValueError("OpenJev probability mapping is incomplete")
        if not isinstance(confidence, (int, float)):
            raise ValueError("OpenJev returned no numeric confidence")
        return decision, float(confidence), clean_probabilities

    @staticmethod
    def _make_ollama_engine() -> Any:
        """Use OpenJev's documented local Ollama factory."""
        from openjev.easy import make_engine

        return make_engine(OLLAMA_BACKEND, model=OLLAMA_MODEL)

    @staticmethod
    def _make_choice(**kwargs: Any) -> Any:
        from openjev import Choice

        return Choice(**kwargs)

    @staticmethod
    def _unavailable(input_summary: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
        return {
            "decision": None,
            "confidence": None,
            "probabilities": None,
            "backend": OLLAMA_BACKEND,
            "model": OLLAMA_MODEL,
            "input_summary": dict(input_summary),
            "status": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
