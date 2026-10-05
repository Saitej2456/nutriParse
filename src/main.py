from pathlib import Path

from extractor import NutritionExtractor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_IMAGE = PROJECT_ROOT / "input" / "food_label.jpg"


def main():

    print("=" * 60)
    print("NUTRIPARSE")
    print("STAGE 1 - PADDLEOCR-VL TEST")
    print("=" * 60)

    if not INPUT_IMAGE.exists():
        print(f"\nImage not found:")
        print(INPUT_IMAGE)
        return

    extractor = NutritionExtractor()

    results = extractor.extract(
        str(INPUT_IMAGE)
    )

    print("\n" + "=" * 60)
    print("RAW PADDLEOCR-VL RESULT")
    print("=" * 60)

    for result in results:
        print(result)


if __name__ == "__main__":
    main()