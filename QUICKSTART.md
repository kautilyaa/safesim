# SafeSim Quick Start Guide

Get SafeSim running in 5 minutes!

## Option 1: Quick Demo (No Installation Required)

If you just want to see how it works:

```bash
# Run the demo with rule-based simplifier (no API keys needed)
python demo.py --mode basic
```

This will show you 3 examples of medical text simplification with entity extraction and verification.

## Option 2: Full Installation

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Step 2: Run the Web Interface

```bash
streamlit run src/ui/app.py
```

Open http://localhost:8501 in your browser. You'll see the SafeSim interface!

### Step 3: Try an Example

1. In the sidebar, select "Example 1: Hypertension"
2. Click "Simplify Text"
3. See the results with safety verification!

## Option 3: Use as a Python Library

```python
from src.safesim_pipeline import SafeSimPipeline

# Initialize (no API key needed for dummy backend)
pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

# Simplify medical text
text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension."
result = pipeline.process(text)

print(f"Original: {result.original_text}")
print(f"Simplified: {result.simplified_text}")
print(f"Safe: {result.is_safe}")
```

## Option 4: Using with OpenAI or Claude

### Setup API Key

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API key
# OPENAI_API_KEY=sk-your-key-here
```

### Run with GPT-4

```python
from src.safesim_pipeline import SafeSimPipeline

pipeline = SafeSimPipeline(
    llm_backend="openai",
    model="gpt-4o-mini",
    api_key="sk-your-key"  # or set in .env
)

result = pipeline.process("Patient prescribed 50mg Atenolol PO q.d.")
print(result.simplified_text)
```

## What You'll See

### Input Example:
```
Patient prescribed 50mg Atenolol PO q.d. for hypertension.
Monitor for bradycardia.
```

### SafeSim Output:
```
✅ SAFE - Verification Score: 100%

Simplified Text:
"Take 50mg of Atenolol by mouth once a day for high blood
pressure. Watch out for slow heart rate."

Extracted Entities:
- 50mg           [DOSAGE]
- Atenolol       [MEDICATION]
- PO             [ROUTE]
- q.d.           [FREQUENCY]
- hypertension   [CONDITION]
- bradycardia    [CONDITION]
```

## Next Steps

- Read README.md for detailed documentation
- Check out LITERATURE_SURVEY.md to understand the research
- Run tests: `python -m pytest tests/ -v`
- Try different LLM backends in the web interface

## Troubleshooting

**Issue**: "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

**Issue**: "Can't find model 'en_core_web_sm'"
```bash
python -m spacy download en_core_web_sm
```

**Issue**: Want better medical entity recognition?
```bash
pip install scispacy
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_md-0.5.3.tar.gz
```

## Demo Modes

```bash
# Basic demo (3 examples)
python demo.py --mode basic

# Batch processing (all examples from JSON)
python demo.py --mode batch

# Interactive mode (enter your own text)
python demo.py --mode interactive
```

## File Structure Overview

```
safesim/
├── src/
│   ├── entity_extraction/    # Extract medical entities
│   ├── simplification/        # LLM simplification
│   ├── verification/          # Verify fact preservation
│   └── ui/                    # Web interface
├── tests/                     # Unit tests
├── examples/                  # Example medical texts
├── demo.py                    # Demo script
└── README.md                  # Full documentation
```

That's it! You're ready to use SafeSim.

For more details, see:
- README.md - Full documentation
- INSTALL.md - Detailed installation guide
- PROJECT_REPORT.md - Academic paper
- LITERATURE_SURVEY.md - Related work
