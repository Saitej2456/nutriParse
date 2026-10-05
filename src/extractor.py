from pathlib import Path
from paddleocr import PaddleOCRVL


class NutritionExtractor:

    def __init__(self):
        print("Loading PaddleOCR-VL...")

        self.pipeline = PaddleOCRVL()

        print("PaddleOCR-VL loaded.")

    def extract(self, image_path: str):
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        print(f"Processing: {image_path}")

        results = self.pipeline.predict(
            input=str(image_path)
        )

        return results