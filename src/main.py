import json
from pathlib import Path

from extractor import NutritionExtractor
from nutrition_parser import NutritionParser


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_IMAGE = PROJECT_ROOT / "input" / "food_label.jpg"
OUTPUT_DIR = PROJECT_ROOT / "output"

RAW_OUTPUT = OUTPUT_DIR / "raw_paddle_output.html"
NUTRITION_OUTPUT = OUTPUT_DIR / "nutrition.json"


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
    all_contents = []

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
    print("NUTRIPARSE - STAGE 2")
    print("Image -> PaddleOCR-VL -> Structured Nutrition")
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
    print("Loading PaddleOCR-VL...")
    print("-" * 60)

    extractor = NutritionExtractor()

    print("\nRunning PaddleOCR-VL...")

    results = extractor.extract(str(INPUT_IMAGE))

    print("PaddleOCR-VL extraction complete.")

    # -----------------------------------------------------
    # Extract useful content from PaddleOCR-VL result
    # -----------------------------------------------------

    raw_content = extract_raw_content(results)

    if not raw_content.strip():
        raise RuntimeError(
            "PaddleOCR-VL returned no parsed content."
        )

    # -----------------------------------------------------
    # Save raw PaddleOCR output
    # -----------------------------------------------------

    RAW_OUTPUT.write_text(
        raw_content,
        encoding="utf-8"
    )

    print("\nRaw parsed output saved to:")
    print(RAW_OUTPUT)

    # -----------------------------------------------------
    # Stage 2: Nutrition parsing
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("Parsing nutrition information...")
    print("-" * 60)

    parser = NutritionParser()

    nutrition_data = parser.parse(raw_content)

    # -----------------------------------------------------
    # Save canonical nutrition JSON
    # -----------------------------------------------------

    NUTRITION_OUTPUT.write_text(
        json.dumps(
            nutrition_data,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # Display result
    # -----------------------------------------------------

    print("\n" + "=" * 60)
    print("CANONICAL NUTRITION DATA")
    print("=" * 60)

    print(
        json.dumps(
            nutrition_data,
            indent=4,
            ensure_ascii=False
        )
    )

    print("=" * 60)
    print("STAGE 2 COMPLETE")
    print("=" * 60)

    print("\nStructured nutrition JSON saved to:")
    print(NUTRITION_OUTPUT)


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()