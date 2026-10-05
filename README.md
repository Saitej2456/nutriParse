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

### Upcoming Stages
The following stages have not yet been implemented:
- Stage 3 — Nutrition normalization and validation
- Stage 4 — Nutri-Score grading
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
│   └── nutrition.json
│
├── src/
│   ├── __init__.py
│   ├── extractor.py
│   ├── nutrition_parser.py
│   └── main.py
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

The parser is deterministic and does not perform nutrition grading.

### `src/main.py`
Acts as the pipeline entry point. It:
1. Locates the input image.
2. Initializes PaddleOCR-VL.
3. Runs image extraction.
4. Extracts the relevant PaddleOCR-VL content.
5. Saves the raw extracted content.
6. Passes the content to NutritionParser.
7. Saves the canonical nutrition JSON.
8. Prints the resulting structured data.

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

After a successful run, two generated files are produced:

```text
output/
├── raw_paddle_output.html
└── nutrition.json
```

- **`raw_paddle_output.html`**: Contains the relevant raw content extracted by PaddleOCR-VL. This file is useful for debugging and understanding what the vision model actually produced.
- **`nutrition.json`**: Contains the structured nutrition information generated by NutritionParser.

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

**No normalization yet**
Values are currently extracted according to the label's displayed basis.
For example: `35 g serving` has not yet been converted to `100 g basis` or another grading-specific basis.

**No advanced validation yet**
The parser does not currently perform comprehensive checks such as:
- Impossible nutrient values
- Relationships between nutrients
- Missing-value classification
- Serving-basis consistency
- Unit conversion
- Per-100g/per-100ml conversion
These will be handled in Stage 3.

**No grading yet**
The project does not currently calculate a Nutri-Score.

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
- **Status:** Planned
- **Planned functionality:** `Canonical Nutrition JSON → Field normalization → Unit normalization → Serving-basis normalization → Missing-value handling → Sanity checks → Validated normalized nutrition`

**Stage 4 — Nutri-Score**
- **Status:** Planned
- **Description:** Implement the official Nutri-Score scoring logic as a deterministic baseline.
- `Normalized Nutrition → Official Scoring Rules → Nutri-Score Points → A - E Grade`

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
Raw HTML/Table Information
       ↓
Nutrition Parser
       ↓
Structured Nutrition JSON
```

This establishes the foundation for the normalization and grading stages that follow.