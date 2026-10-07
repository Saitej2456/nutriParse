# NutriParse

NutriParse is an AI-based food nutrition analysis pipeline that extracts nutrition information from food-label images and prepares the extracted information for downstream nutrition grading.

The project is being developed incrementally as part of an Advanced Deep Learning course project.

---

## Current Status

### Stage 1 — Image-to-Text Extraction ✅

A pretrained **PaddleOCR-VL** model is used to process a food-label image and extract its document and table information.

```text
Food Label Image
        ↓
   PaddleOCR-VL
        ↓
Raw Structured / HTML Output
```

### Stage 2 — Structured Nutrition Extraction ✅

The raw PaddleOCR-VL output is processed using a deterministic Python parser.

```text
Raw PaddleOCR-VL Output
        ↓
  HTML Cleaning
        ↓
Text Normalization
        ↓
Regex-based Field Extraction
        ↓
Canonical Nutrition JSON
```

The current pipeline successfully extracts the nutrition information from the test food label.

### Stage 3 — Nutrition Normalization and Validation ✅

The canonical nutrition JSON is processed by a deterministic normalizer.

```text
Canonical Nutrition JSON
        ↓
  Unit normalization
        ↓
  Basis normalization (per-serving → per 100 g / per 100 ml)
        ↓
  Missing-value handling (null ≠ zero)
        ↓
  Sanity + cross-field validation
        ↓
Validated Normalized Nutrition JSON
```

### Stage 4 — Deterministic Original Nutri-Score ✅

Stage 4 calculates a deterministic, auditable **original/pre-2023 Nutri-Score** for supported general foods from the normalized per-100 g values.

```text
Normalized Nutrition JSON
        ↓
Original Nutri-Score tables
        ↓
Negative points: energy, sugars, saturated fat, sodium
Positive points: fibre, protein
        ↓
Score and grade A-E
```

The implementation uses sodium (not salt) and converts normalized kcal to kJ locally for the energy lookup. Fruit, vegetable, legume, and nut (FVLN) percentage is not available from the current extraction pipeline, is never estimated, and is explicitly recorded as unavailable. Consequently, every Stage 4 result includes partial/incomplete-calculation metadata even when all scorable nutrients are present.

This is a research baseline, not the revised/current 2023 Nutri-Score algorithm. It supports the general-food, per-100 g path only. Beverage, cheese, fat/oil, nut/seed, and other category-specific rules are intentionally unsupported because NutriParse does not infer a food category.

### Upcoming Stages
The following stages have not yet been implemented:
- Stage 5 — JEV-based grading
- Stage 6 — Confidence-based JEV/deterministic fallback
- Stage 7 — End-to-end evaluation

---

## Project Architecture

The planned overall architecture is:

```text
                    ┌─────────────────────┐
                    │   Food Label Image  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    PaddleOCR-VL     │
                    │  Image Extraction   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Nutrition Parser    │
                    │ Structured Extract. │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Normalization    │
                    │     (Stage 3)       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Nutrition Grading │
                    │      / JEV          │
                    │     (Future)        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Final Grade      │
                    │      A - E          │
                    └─────────────────────┘
```

---

## Current Pipeline

The currently implemented pipeline is:

```text
input/food_label.jpg
        │
        ▼
NutritionExtractor
        │
        ▼
PaddleOCR-VL
        │
        ▼
Raw HTML / Table Content
        │
        ▼
NutritionParser
        │
        ▼
output/nutrition.json
```

---

## Project Structure

```text
nutriParse/
│
├── input/
│   └── food_label.jpg
│
├── output/
│   ├── raw_paddle_output.html
│   ├── nutrition.json
│   ├── normalized_nutrition.json
│   └── nutri_score.json
│
├── src/
│   ├── __init__.py
│   ├── extractor.py
│   ├── nutrition_parser.py
│   ├── nutrition_normalizer.py
│   ├── nutri_score.py
│   ├── main.py
│   └── tests/
│       ├── __init__.py
│       ├── test_normalizer.py
│       └── test_nutri_score.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Components

### `src/extractor.py`
Responsible for running PaddleOCR-VL on the input image.

```text
Image
  ↓
PaddleOCR-VL
  ↓
PaddleOCR-VL Result
```

The extractor does not perform nutrition-specific interpretation. Its responsibility is to obtain the raw information from the image.

### `src/nutrition_parser.py`
Responsible for converting the raw PaddleOCR-VL output into a structured nutrition representation.

PaddleOCR-VL currently returns table content as HTML. The parser therefore performs:
1. HTML tag removal
2. HTML entity decoding
3. Whitespace normalization
4. Numeric parsing
5. Nutrition-field extraction

The parser currently extracts:
- Calories
- Total fat
- Saturated fat
- Trans fat
- Cholesterol
- Sodium
- Total carbohydrate
- Dietary fiber
- Total sugars
- Added sugars
- Protein
- Vitamin D
- Calcium
- Iron
- Potassium
- Serving size

The parser is deterministic and does not perform normalization or grading.

### `src/nutrition_normalizer.py`
Responsible for Stage 3: normalizing and validating the canonical nutrition dict.

It performs:
1. **Basis determination** — reads serving size (g or ml) and computes the scale factor to reach 100 g or 100 ml.
2. **Value scaling** — multiplies every per-serving nutrient by the scale factor.
3. **Missing-value preservation** — `null` stays `null`; only an explicit `0` on the label becomes `0`.
4. **Sanity validation** — flags negative values, non-finite numbers, unrecognized units.
5. **Cross-field consistency** — warns when e.g. saturated fat > total fat.
6. **Optional energy check** — warns when macronutrient energy deviates from stated calories by > 20%.

The normalizer never modifies the original extracted values.

### `src/tests/test_normalizer.py`
39 unit tests covering all normalization and validation rules. Run with:
```bash
python -m pytest src\tests\test_normalizer.py -v
```

### `src/main.py`
Acts as the pipeline entry point. It:
1. Locates the input image.
2. Initializes PaddleOCR-VL (Stage 1).
3. Runs image extraction.
4. Extracts the relevant PaddleOCR-VL content.
5. Saves the raw extracted content.
6. Passes the content to `NutritionParser` (Stage 2).
7. Saves `output/nutrition.json`.
8. Passes the parsed data to `NutritionNormalizer` (Stage 3).
9. Saves `output/normalized_nutrition.json`.
10. Calculates deterministic original Nutri-Score points and grade (Stage 4).
11. Saves `output/nutri_score.json`.
12. Prints the normalized data, score breakdown, and validation summary.

---

## PaddleOCR-VL Result Handling

The installed PaddleOCR-VL version returns a result object that behaves like a dictionary. The relevant structure is:

```text
results
    │
    └── PaddleOCRVLResult
            │
            └── ["parsing_res_list"]
                    │
                    ├── PaddleOCRVLBlock
                    │      ├── label
                    │      └── content
                    │
                    └── ...
```

The result therefore uses dictionary-style access:
```python
result["parsing_res_list"]
```
rather than:
```python
result.parsing_res_list
```

The individual blocks expose their information through:
```python
block.label
block.content
```

The content returned by the table blocks is HTML. For example:
```html
<table>
    <tr>
        <td>Nutrition Facts</td>
        ...
    </tr>
</table>
```
The nutrition parser removes this markup before performing field extraction.

---

## Canonical Nutrition Output

The current parser produces a JSON object with the following structure:

```json
{
    "serving_size": {
        "amount": 35,
        "unit": "g"
    },
    "nutrition": {
        "calories": 140,
        "total_fat_g": 3,
        "saturated_fat_g": 0,
        "trans_fat_g": 0,
        "cholesterol_mg": 0,
        "sodium_mg": 0,
        "carbohydrate_g": 23,
        "fiber_g": 4,
        "total_sugars_g": 5,
        "added_sugars_g": 0,
        "protein_g": 4,
        "vitamin_d_mcg": 0,
        "calcium_mg": 14,
        "iron_mg": 1,
        "potassium_mg": 195
    }
}
```

The values above correspond to the current test food-label image. The implementation does not hardcode these values. They are extracted from the PaddleOCR-VL output.

---

## Installation

**1. Create the virtual environment**

Python 3.12 is currently used for this project.

```bash
python -m venv nutriparse-env
```

Activate it:
```bash
.\nutriparse-env\Scripts\Activate.ps1
```

**2. Install dependencies**

Install the required packages:
```bash
pip install -r requirements.txt
```

The project currently uses:
- PaddlePaddle
- PaddleOCR with document parsing support

---

## Running the Project

Make sure the virtual environment is activated:
```bash
.\nutriparse-env\Scripts\Activate.ps1
```

Then run:
```bash
python src\main.py
```

The pipeline will process:
`input/food_label.jpg`

---

## Output

After a successful run, four generated files are produced:

```text
output/
├── raw_paddle_output.html
├── nutrition.json
├── normalized_nutrition.json
└── nutri_score.json
```

- **`raw_paddle_output.html`**: Raw HTML/table content extracted by PaddleOCR-VL. Useful for debugging OCR output.
- **`nutrition.json`**: Canonical per-serving nutrition JSON from Stage 2.
- **`normalized_nutrition.json`**: Fully normalized, validated JSON from Stage 3. This is the input for future grading stages.
- **`nutri_score.json`**: Auditable Stage 4 original/pre-2023 Nutri-Score breakdown for the supported general-food path. It records missing values, FVLN unavailability, and unsupported-category limitations.

---

## Example Execution

A successful execution follows this general flow:

```text
============================================================
NUTRIPARSE - STAGE 2
Image -> PaddleOCR-VL -> Structured Nutrition
============================================================

Input image:
...\input\food_label.jpg

Loading PaddleOCR-VL...

PaddleOCR-VL loaded.

Running PaddleOCR-VL...

PaddleOCR-VL extraction complete.

Raw parsed output saved to:
...\output\raw_paddle_output.html

------------------------------------------------------------
Parsing nutrition information...
------------------------------------------------------------

============================================================
CANONICAL NUTRITION DATA
============================================================

{
    "serving_size": {
        "amount": 35,
        "unit": "g"
    },
    "nutrition": {
        "calories": 140,
        "total_fat_g": 3,
        "saturated_fat_g": 0,
        "trans_fat_g": 0,
        "cholesterol_mg": 0,
        "sodium_mg": 0,
        "carbohydrate_g": 23,
        "fiber_g": 4,
        "total_sugars_g": 5,
        "added_sugars_g": 0,
        "protein_g": 4,
        "vitamin_d_mcg": 0,
        "calcium_mg": 14,
        "iron_mg": 1,
        "potassium_mg": 195
    }
}

============================================================
STAGE 2 COMPLETE
============================================================
```

---

## Design Principles

**1. AI for interpretation**
PaddleOCR-VL is used where visual understanding and document interpretation are required.
`Image → Information`

**2. Deterministic code for structured extraction**
Once the information has been extracted into text/table form, deterministic parsing is used to extract the known nutrition fields.
`Extracted Text → Structured Fields`
This makes the current Stage 2 behavior reproducible and easier to debug.

**3. Separate extraction from grading**
The current parser does not decide whether food is healthy or unhealthy. It only answers:
*What nutrition information is present on this label?*
Grading will be implemented separately.

---

## Current Limitations

The current implementation is intentionally an early pipeline stage.

**Stage 4 category limits**
The current deterministic score is deliberately restricted to general foods normalized per 100 g. It does not infer beverage, cheese, fat/oil, nut/seed, or other special categories, so their category-specific original Nutri-Score rules are not applied.

**FVLN percentage unavailable**
The pipeline does not extract fruit, vegetable, legume, and nut percentage. Stage 4 never infers, estimates, or equates that percentage with zero; instead, it records the component as unavailable and marks the resulting baseline score as partial.

**No JEV integration yet**
JEV will be integrated in a later stage after the nutrition data has been normalized and validated.

---

## Development Roadmap

**Stage 1 — Image Extraction**
- **Status:** Complete
- `Food Image → PaddleOCR-VL → Raw extracted content`

**Stage 2 — Structured Nutrition Extraction**
- **Status:** Complete
- `Raw extracted content → HTML cleaning → Text normalization → Regex-based extraction → Canonical Nutrition JSON`

**Stage 3 — Nutrition Normalization**
- **Status:** ✅ Complete
- **Pipeline:** `Canonical Nutrition JSON → Basis determination → Per-100g/ml scaling → Missing-value preservation → Sanity validation → Cross-field consistency → Validated Normalized Nutrition JSON`
- **Output:** `output/normalized_nutrition.json`
- **Tests:** 39 unit tests, all passing (`src/tests/test_normalizer.py`)
- **Canonical units:** calories (kcal), fat/carbohydrate/fiber/protein/sugars (g), sodium/cholesterol/calcium/iron/potassium (mg), vitamin D (mcg)
- **Normalization basis:** per 100 g for solid foods (g serving), per 100 ml for liquids (ml serving)
- **Missing vs zero:** `null` = field absent from label; `0` = field present and zero — these are explicitly kept distinct

**Stage 4 — Nutri-Score**
- **Status:** ✅ Complete (general-food research baseline)
- **Description:** Deterministic original/pre-2023 scoring for energy, total sugars, saturated fat, sodium, fibre, and protein. FVLN is explicitly unavailable and special-category rules are unsupported.
- **Pipeline:** `Normalized Nutrition → Original Scoring Rules → Auditable Points → A - E Grade`
- **Output:** `output/nutri_score.json`

**Stage 5 — JEV Integration**
- **Status:** Planned
- **Description:** JEV will receive structured nutrition information together with the relevant grading instructions.
- `Normalized Nutrition + Grading Instructions → JEV → Grade + Score + Confidence`

**Stage 6 — Confidence-Gated Hybrid Grading**
- **Status:** Planned
- **Description:** The planned architecture is:

```text
                 ┌───────────────┐
                 │  Normalized   │
                 │   Nutrition   │
                 └───────┬───────┘
                         │
                         ▼
                    ┌─────────┐
                    │   JEV   │
                    └────┬────┘
                         │
                 Grade + Confidence
                         │
                 ┌───────┴───────┐
                 │               │
            High confidence   Low confidence
                 │               │
                 ▼               ▼
            JEV result    Deterministic
                           rule engine
                 │               │
                 └───────┬───────┘
                         ▼
                    Final Grade
```
*The confidence threshold will be determined using validation data rather than being arbitrarily chosen.*

---

## Current Milestone

At the current checkpoint, NutriParse can successfully perform:

```text
Food Label Image
       ↓
PaddleOCR-VL
       ↓
Nutrition Parser
       ↓
Canonical Nutrition JSON
       ↓
Nutrition Normalizer
       ↓
Validated / Normalized Nutrition
       ↓
Deterministic Original Nutri-Score
       ↓
Partial Baseline Grade A-E
```

The current milestone includes normalization and deterministic grading. Next work is focused on the later AI-based grading and hybrid stages.
