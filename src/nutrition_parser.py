import re
from typing import Optional


class NutritionParser:
    """
    Stage 2:
        PaddleOCR-VL raw content (HTML)
        ->
        Canonical nutrition JSON

    The parser:
        1. Strips HTML tags (PaddleOCR-VL returns HTML table markup)
        2. Normalizes whitespace
        3. Extracts nutrition fields with regex

    This parser does NOT perform normalization or grading.
    Its only responsibility is extracting nutrition fields
    from the raw HTML produced by PaddleOCR-VL.
    """

    # ---------------------------------------------------------
    # HTML stripping
    # ---------------------------------------------------------

    @staticmethod
    def strip_html(text: str) -> str:
        """
        Remove all HTML tags and unescape HTML entities.

        PaddleOCR-VL returns content as HTML table markup, e.g.:

            <table><tr><td>Nutrition Facts</td></tr>…</table>

        After stripping:

            Nutrition Facts …
        """

        import html as html_module

        # Replace block-level tags with newlines to preserve word boundaries
        text = re.sub(r"<(?:tr|/tr|p|/p|br\s*/?)>", "\n", text, flags=re.IGNORECASE)

        # Replace all remaining tags with a space
        text = re.sub(r"<[^>]+>", " ", text)

        # Unescape HTML entities (&amp; &lt; etc.)
        text = html_module.unescape(text)

        return text

    # ---------------------------------------------------------
    # Text normalization
    # ---------------------------------------------------------

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Normalize whitespace while preserving content.
        """

        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # ---------------------------------------------------------
    # Number parsing
    # ---------------------------------------------------------

    @staticmethod
    def parse_number(value: str) -> Optional[float]:
        """
        Convert a numeric string into int or float.
        """

        if value is None:
            return None

        value = value.strip()

        try:
            number = float(value)

            if number.is_integer():
                return int(number)

            return number

        except ValueError:
            return None

    # ---------------------------------------------------------
    # Regex extraction
    # ---------------------------------------------------------

    @staticmethod
    def extract_value(
        text: str,
        *patterns: str,
        flags: int = re.IGNORECASE,
    ) -> Optional[float]:
        """
        Search text using one or more regular expression patterns
        and return the first captured numeric value.

        Multiple patterns can be supplied to handle different
        label orderings (e.g. "Calories 140" vs "140 Calories").
        The first pattern that produces a match wins.
        """

        for pattern in patterns:
            match = re.search(pattern, text, flags)

            if match:
                return NutritionParser.parse_number(match.group(1))

        return None

    # ---------------------------------------------------------
    # Serving size
    # ---------------------------------------------------------

    @staticmethod
    def parse_serving_size(text: str) -> dict:
        """
        Extract the gram-based serving size.

        Examples handled:

            Serving size 1/4 cup (35g)   ->  {"amount": 35, "unit": "g"}
            Serving size 250 ml          ->  {"amount": 250, "unit": "ml"}
        """

        # Preferred: value in parentheses, e.g. (35g)
        match = re.search(
            r"Serving\s+size.*?\(([\d.]+)\s*(g|ml)\)",
            text,
            re.IGNORECASE,
        )

        if match:
            return {
                "amount": NutritionParser.parse_number(match.group(1)),
                "unit": match.group(2).lower(),
            }

        # Fallback: bare value without parentheses
        match = re.search(
            r"Serving\s+size.*?([\d.]+)\s*(g|ml)\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return {
                "amount": NutritionParser.parse_number(match.group(1)),
                "unit": match.group(2).lower(),
            }

        return {
            "amount": None,
            "unit": None,
        }

    # ---------------------------------------------------------
    # Main parse method
    # ---------------------------------------------------------

    def parse(self, raw_html: str) -> dict:
        """
        Convert PaddleOCR-VL HTML output into canonical nutrition JSON.

        Step 1: Strip HTML tags (PaddleOCR-VL returns HTML table markup)
        Step 2: Normalize whitespace
        Step 3: Extract fields with regex
        """

        # Strip HTML, then normalize whitespace
        text = self.strip_html(raw_html)
        text = self.clean_text(text)

        nutrition = {

            # Calories can appear as "Calories 140" or "140 Calories"
            # depending on the OCR layout of the label.
            "calories": self.extract_value(
                text,
                r"Calories\s+([\d.]+)",
                r"([\d.]+)\s+Calories",
            ),

            "total_fat_g": self.extract_value(
                text,
                r"Total\s+Fat\s+([\d.]+)\s*g\b",
            ),

            "saturated_fat_g": self.extract_value(
                text,
                r"Saturated\s+Fat\s+([\d.]+)\s*g\b",
            ),

            "trans_fat_g": self.extract_value(
                text,
                r"Trans\s+Fat\s+([\d.]+)\s*g\b",
            ),

            "cholesterol_mg": self.extract_value(
                text,
                r"Cholesterol\s+([\d.]+)\s*mg\b",
            ),

            "sodium_mg": self.extract_value(
                text,
                r"Sodium\s+([\d.]+)\s*mg\b",
            ),

            "carbohydrate_g": self.extract_value(
                text,
                r"Total\s+Carbohydrate\s+([\d.]+)\s*g\b",
            ),

            "fiber_g": self.extract_value(
                text,
                r"Dietary\s+Fiber\s+([\d.]+)\s*g\b",
            ),

            "total_sugars_g": self.extract_value(
                text,
                r"Total\s+Sugars\s+([\d.]+)\s*g\b",
            ),

            "added_sugars_g": self.extract_value(
                text,
                r"Includes\s+([\d.]+)\s*g\s+Added\s+Sugars",
            ),

            "protein_g": self.extract_value(
                text,
                r"Protein\s+([\d.]+)\s*g\b",
            ),

            "vitamin_d_mcg": self.extract_value(
                text,
                r"Vitamin\s+D\s+([\d.]+)\s*mcg\b",
            ),

            "calcium_mg": self.extract_value(
                text,
                r"Calcium\s+([\d.]+)\s*mg\b",
            ),

            "iron_mg": self.extract_value(
                text,
                r"Iron\s+([\d.]+)\s*mg\b",
            ),

            "potassium_mg": self.extract_value(
                text,
                r"Potassium\s+([\d.]+)\s*mg\b",
            ),
        }

        return {
            "serving_size": self.parse_serving_size(text),
            "nutrition": nutrition,
        }