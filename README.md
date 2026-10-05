# AI Food Nutrition Grading Pipeline

An experimental deep-learning pipeline for extracting nutritional
information from packaged-food labels and assigning a nutritional grade.

## Current Stage

Stage 1:

Food Image
    ↓
PaddleOCR-VL
    ↓
Structured Output
    ↓
JSON

## Project Structure

```text
nutriParse/
│
├── input/
│   └── food_label.jpg
│
├── output/
│   └── nutrition.json
│
├── src/
│   ├── __init__.py
│   ├── extractor.py
│   └── main.py
│
├── requirements.txt
├── README.md
└── .gitignore