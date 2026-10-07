import json
from pathlib import Path

from extractor import NutritionExtractor
from nutrition_parser import NutritionParser
from nutrition_normalizer import NutritionNormalizer
from nutri_score import NutriScoreCalculator


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_IMAGE = PROJECT_ROOT / "input" / "food_label.jpg"
OUTPUT_DIR  = PROJECT_ROOT / "output"

RAW_OUTPUT        = OUTPUT_DIR / "raw_paddle_output.html"
NUTRITION_OUTPUT  = OUTPUT_DIR / "nutrition.json"
NORMALIZED_OUTPUT = OUTPUT_DIR / "normalized_nutrition.json"
NUTRI_SCORE_OUTPUT = OUTPUT_DIR / "nutri_score.json"


# ---------------------------------------------------------
# PaddleOCR-VL result extraction
# ---------------------------------------------------------

def extract_raw_content(results) -> str:
    """
    Extract text/table content from PaddleOCR-VL results.

    Verified structure (PaddleOCR-VL 1.6 / PaddleX):

        results                     -> list
          results[0]                -> PaddleOCRVLResult (dict subclass)
            results[0]["parsing_res_list"]  -> list of PaddleOCRVLBlock
              block.label           -> str  e.g. "table"
              block.content         -> str  HTML e.g. "<table>…</table>"

    IMPORTANT:
        PaddleOCRVLResult supports dict-style key access:
            result["parsing_res_list"]   ✓
        It does NOT support attribute-style access:
            result.parsing_res_list      ✗  (AttributeError)

        PaddleOCRVLBlock items inside the list DO support attribute access:
            block.label    ✓
            block.content  ✓
    """

    table_contents = []
    all_contents   = []

    for result in results:
        # Use dict-key access — attribute access raises AttributeError
        parsing_res_list = result["parsing_res_list"]

        for block in parsing_res_list:
            content = block.content

            if not content:
                continue

            content = str(content).strip()

            if not content:
                continue

            all_contents.append(content)

            if block.label and block.label.lower() == "table":
                table_contents.append(content)

    # Nutrition information is normally inside a table.
    # Prefer table content when available.
    if table_contents:
        return "\n".join(table_contents)

    # Otherwise fall back to all extracted content.
    return "\n".join(all_contents)


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def main():
    print("=" * 60)
    print("NUTRIPARSE")
    print("Stage 1: Image -> PaddleOCR-VL")
    print("Stage 2: OCR output -> Canonical Nutrition JSON")
    print("Stage 3: Canonical JSON -> Normalized + Validated JSON")
    print("Stage 4: Normalized JSON -> Original Nutri-Score (general food)")
    print("=" * 60)

    # -----------------------------------------------------
    # Create output directory
    # -----------------------------------------------------

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------
    # Check input image
    # -----------------------------------------------------

    if not INPUT_IMAGE.exists():
        raise FileNotFoundError(
            f"Input image not found:\n{INPUT_IMAGE}"
        )

    print(f"\nInput image:")
    print(INPUT_IMAGE)

    # -----------------------------------------------------
    # Stage 1: PaddleOCR-VL extraction
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("Stage 1 — PaddleOCR-VL extraction")
    print("-" * 60)

    extractor = NutritionExtractor()

    print("\nRunning PaddleOCR-VL...")

    results = extractor.extract(str(INPUT_IMAGE))

    print("PaddleOCR-VL extraction complete.")

    # Extract useful content from PaddleOCR-VL result
    raw_content = extract_raw_content(results)

    if not raw_content.strip():
        raise RuntimeError(
            "PaddleOCR-VL returned no parsed content."
        )

    # Save raw PaddleOCR output
    RAW_OUTPUT.write_text(raw_content, encoding="utf-8")

    print(f"\nRaw parsed output saved to:\n{RAW_OUTPUT}")

    # -----------------------------------------------------
    # Stage 2: Nutrition parsing
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("Stage 2 — Nutrition parsing")
    print("-" * 60)

    parser = NutritionParser()

    nutrition_data = parser.parse(raw_content)

    # Save canonical nutrition JSON (Stage 2 output preserved)
    NUTRITION_OUTPUT.write_text(
        json.dumps(nutrition_data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("CANONICAL NUTRITION DATA (Stage 2)")
    print("=" * 60)
    print(json.dumps(nutrition_data, indent=4, ensure_ascii=False))
    print(f"\nSaved to:\n{NUTRITION_OUTPUT}")

    # -----------------------------------------------------
    # Stage 3: Normalization and validation
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("Stage 3 — Normalization and validation")
    print("-" * 60)

    normalizer = NutritionNormalizer(check_energy_consistency=True)

    norm_result = normalizer.normalize(nutrition_data)

    # Build the output dict with source provenance
    normalized_output = norm_result.to_dict(
        input_image=str(INPUT_IMAGE.relative_to(PROJECT_ROOT))
    )

    # Save normalized output
    NORMALIZED_OUTPUT.write_text(
        json.dumps(normalized_output, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("NORMALIZED NUTRITION DATA (Stage 3)")
    print("=" * 60)
    print(json.dumps(normalized_output, indent=4, ensure_ascii=False))
    print(f"\nSaved to:\n{NORMALIZED_OUTPUT}")

    # -----------------------------------------------------
    # Stage 4: Deterministic original Nutri-Score
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("Stage 4 — Deterministic original Nutri-Score")
    print("-" * 60)

    nutri_score = NutriScoreCalculator().calculate(normalized_output)
    NUTRI_SCORE_OUTPUT.write_text(
        json.dumps(nutri_score, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("NUTRI-SCORE (Stage 4)")
    print("=" * 60)
    print(json.dumps(nutri_score, indent=4, ensure_ascii=False))
    print(f"\nSaved to:\n{NUTRI_SCORE_OUTPUT}")

    # -----------------------------------------------------
    # Validation summary
    # -----------------------------------------------------

    print("\n" + "=" * 60)
    if norm_result.is_valid():
        print("STAGE 3 VALIDATION: PASSED (no normalization errors)")
    else:
        print("STAGE 3 VALIDATION: FAILED")
    print("=" * 60)

    validation = normalized_output["validation"]

    if validation["errors"]:
        print("\nErrors:")
        for e in validation["errors"]:
            print(f"  [{e['code']}] {e['message']}")

    if validation["warnings"]:
        print("\nWarnings:")
        for w in validation["warnings"]:
            print(f"  [{w['code']}] {w['message']}")

    if nutri_score["warnings"]:
        print("\nStage 4 warnings:")
        for warning in nutri_score["warnings"]:
            print(f"  {warning}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
