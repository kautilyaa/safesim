# SafeSim: Safe Medical Text Simplification with Neuro-Symbolic Verification

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/Status-Active-success" alt="Active">
</p>

SafeSim is a medical text simplification system that uses a **neuro-symbolic approach** to convert complex discharge summaries and clinical notes into patient-friendly language while **guaranteeing** the preservation of critical medical facts.

## 🎯 Problem Statement

Traditional neural text simplification models often suffer from:
- **Hallucinations**: Adding information that wasn't in the original text
- **Omissions**: Dropping critical medical details (dosages, medication names, vitals)
- **Lack of Safety Guarantees**: No verification that important facts are preserved

In medical contexts, these failures can have serious consequences. A patient who doesn't know their correct dosage or medication schedule could face health risks.

## 💡 Our Solution: Neuro-Symbolic Pipeline

SafeSim combines neural language models with symbolic verification:

```
┌─────────────────────────────────────────────────────────────┐
│                    SAFESIM PIPELINE                          │
└─────────────────────────────────────────────────────────────┘

Input: "Patient prescribed 50mg Atenolol PO q.d. for hypertension."

    ↓
┌─────────────────────────────────┐
│ 1. Entity Extraction (Symbolic) │  ← Regex + NER
├─────────────────────────────────┤
│ Extracted: [50mg, Atenolol,    │
│             PO, q.d.]           │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. LLM Simplification (Neural)  │  ← GPT-4, Claude, BART
├─────────────────────────────────┤
│ "Take 50mg of Atenolol by mouth │
│  once a day for high blood      │
│  pressure."                     │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. Logic Verification (Symbolic)│  ← Deterministic checks
├─────────────────────────────────┤
│ ✅ 50mg found                   │
│ ✅ Atenolol found               │
│ ✅ q.d. → "once a day" (OK)     │
│ Score: 100% - SAFE              │
└─────────────────────────────────┘

Output: ✅ Verified safe simplification
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/safesim.git
cd safesim

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Run the Web Interface

```bash
streamlit run src/ui/app.py
```

Then open http://localhost:8501 in your browser.

### Run Tests

```bash
python -m pytest tests/ -v
```

### Use as a Library

```python
from src.safesim_pipeline import SafeSimPipeline

# Initialize with dummy backend (no API key needed)
pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

# Or use OpenAI
# pipeline = SafeSimPipeline(llm_backend="openai", api_key="sk-...")

# Process medical text
text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension."
result = pipeline.process(text)

print(f"Original: {result.original_text}")
print(f"Simplified: {result.simplified_text}")
print(f"Safe: {result.is_safe}")
print(f"Score: {result.verification['score']:.0%}")
```

## 📊 Features

### 1. Multi-Entity Extraction
- **Dosages**: 50mg, 10 units, 2 tablets
- **Medications**: Atenolol, Metformin, Insulin
- **Vitals**: 120/80 mmHg, 98.6°F, 72 bpm
- **Frequencies**: q.d., b.i.d., twice daily
- **Routes**: PO, IV, subcutaneous

### 2. Multiple LLM Backends
- OpenAI (GPT-4, GPT-3.5)
- Anthropic Claude
- HuggingFace (BART, T5)
- Dummy (rule-based, for testing)

### 3. Configurable Strictness
- **High**: All critical entities must match exactly (95%+ similarity)
- **Medium**: Minor variations allowed (85%+ similarity)
- **Low**: Semantic equivalence accepted (75%+ similarity)

### 4. Safety Verification
- Deterministic entity preservation checks
- Acceptable transformation dictionary (e.g., "q.d." → "once a day")
- Fuzzy matching for spacing variations
- Warning generation for missing entities

## 📚 Literature Survey

### Related Work

SafeSim builds on recent advances in medical NLP and controllable text generation.

#### A. Datasets (Where we get data)

1. **Med-EASi** (Basu et al., AAAI 2023)
   - Finely annotated dataset for medical text simplification
   - Expert vs. Layman versions with tagged elaborations and replacements
   - **Why we use it**: Explicitly marks medical jargon transformations
   - Paper: "Med-EASi: Finely Annotated Dataset and Models for Controllable Simplification of Medical Texts"

2. **Cochrane/MultiSim** (Van den Bercken et al., EACL 2023)
   - Paragraph-level medical abstracts from Cochrane database
   - **Why we use it**: Good for summarization-style simplification
   - Paper: "NapSS: Paragraph-level Medical Text Simplification"

#### B. Baselines (What we compare against)

1. **BART-UL** (Devaraj et al., EMNLP 2021)
   - Uses BART with unlikelihood training to punish jargon
   - **Limitation**: Strong on readability but weak on fact preservation
   - Paper: "Paragraph-level Medical Text Simplification"

2. **Standard T5/Pegasus**
   - Fine-tuned seq2seq models on WikiLarge or medical corpora
   - **Limitation**: Treats medical text like general text, smooths out critical details
   - Used as baseline in many medical NLP benchmarks

3. **GPT-3 Few-Shot** (Brown et al., NeurIPS 2020)
   - In-context learning for simplification
   - **Limitation**: Can hallucinate, no verification mechanism

#### C. Similar Works (Closest to our approach)

1. **Fact-Controlled Hallucination Detection** (Interspeech 2025)
   - Detects hallucinations in medical summarization
   - **Similarity**: Also focuses on fact verification
   - **Difference**: They detect errors *after* generation (diagnosis). We *prevent/fix* them during generation (mitigation).

2. **TESLEA** (JMIR 2022) - Reinforcement Learning
   - Uses RL rewards to improve simplicity while preserving facts
   - **Similarity**: Also aims for safe simplification
   - **Difference**: Uses abstract reward functions (learned). We use symbolic constraints (deterministic, interpretable).
   - Paper: "Medical Text Simplification Using Reinforcement Learning"

3. **Entity-Constrained Summarization** (ACL 2022)
   - Constrains summarization to include key entities
   - **Similarity**: Entity-centric approach
   - **Difference**: Focuses on extractive summarization. We focus on abstractive simplification with verification.

### Our Novelty

**SafeSim introduces a Neuro-Symbolic Validation Loop:**

1. **Symbolic Entity Extraction**: Deterministic pattern matching guarantees we capture critical facts
2. **Neural Simplification**: LLMs provide natural, fluent simplifications
3. **Symbolic Verification**: Hard constraints ensure no critical information is lost

This is different from:
- Pure neural approaches (BART-UL, T5) that have no safety guarantees
- Pure symbolic approaches (rule-based) that lack fluency and coverage
- RL approaches (TESLEA) that use soft, learned rewards instead of hard constraints

**Key Advantage**: SafeSim provides **interpretable, deterministic safety guarantees** that are crucial for clinical deployment.

## 🏗️ Architecture

### Project Structure

```
safesim/
├── src/
│   ├── entity_extraction/
│   │   ├── __init__.py
│   │   └── extractor.py          # NER + regex entity extraction
│   ├── simplification/
│   │   ├── __init__.py
│   │   └── llm_simplifier.py     # LLM backends (GPT, Claude, BART)
│   ├── verification/
│   │   ├── __init__.py
│   │   └── logic_checker.py      # Symbolic fact verification
│   ├── ui/
│   │   ├── __init__.py
│   │   └── app.py                # Streamlit web interface
│   ├── __init__.py
│   └── safesim_pipeline.py       # Main orchestration pipeline
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py          # Unit tests
├── examples/
│   └── medical_texts.json        # Example medical texts
├── data/                         # (Optional) Training data
├── requirements.txt
└── README.md
```

### Component Details

#### 1. Entity Extraction (`src/entity_extraction/extractor.py`)

Uses a hybrid approach:
- **spaCy NER**: For medications, conditions (using en_core_sci_md if available)
- **Regex patterns**: For dosages (50mg), frequencies (q.d.), vitals (120/80 mmHg)

**Why hybrid?**
- Pure NER misses structured entities like dosages
- Pure regex misses context-dependent entities like medication names

#### 2. LLM Simplification (`src/simplification/llm_simplifier.py`)

Supports multiple backends:
- **OpenAI GPT-4**: Best quality, requires API key
- **Anthropic Claude**: Great for safety, requires API key
- **HuggingFace BART/T5**: Local deployment, good for research
- **Dummy (Rule-based)**: For testing without API keys

System prompt emphasizes:
```
CRITICAL RULES:
1. NEVER omit numerical values (dosages, vitals, measurements)
2. NEVER omit medication names
3. NEVER change the meaning of medical instructions
```

#### 3. Logic Verification (`src/verification/logic_checker.py`)

Deterministic checks:
1. **Exact match**: Is "50mg" in the simplified text?
2. **Normalized match**: Remove spaces/punctuation, then check
3. **Acceptable transforms**: Is "q.d." → "once a day" acceptable?
4. **Fuzzy dosage match**: Does "50mg" match "50 mg"?
5. **Medication root**: Is "atenolol" present even if case differs?

**Scoring**: Jaccard similarity between original and simplified entity sets

#### 4. Pipeline (`src/safesim_pipeline.py`)

Orchestrates the three components:
```python
1. entities = extractor.extract(text)
2. simplified = simplifier.simplify(text, entities)
3. verification = checker.verify(entities, simplified)
4. if not safe and retries < max:
       simplified = simplifier.simplify(text, entities + missing)
       verification = checker.verify(entities, simplified)
```

## 📈 Evaluation Metrics

SafeSim can be evaluated on multiple dimensions:

### 1. Safety Metrics
- **Entity Preservation Rate**: % of critical entities preserved
- **Hallucination Rate**: % of generated entities not in original
- **Verification Score**: Jaccard similarity of entity sets

### 2. Simplification Quality
- **Readability**: Flesch-Kincaid Grade Level
- **Compression**: Length reduction ratio
- **Fluency**: Perplexity scores

### 3. Clinical Utility
- **User studies**: Can patients understand the simplified text?
- **Expert evaluation**: Do doctors approve of the simplifications?
- **Task success**: Can patients follow instructions correctly?

## 🔬 Experimental Setup

### Datasets
1. **Med-EASi** for training and evaluation
2. **Custom test set** of 50 discharge summaries (see `examples/medical_texts.json`)

### Baselines
1. BART-large fine-tuned on Med-EASi
2. T5-base fine-tuned on Med-EASi
3. GPT-3.5 few-shot
4. Rule-based simplification

### Our Approach
- SafeSim with different LLM backends
- Ablation: SafeSim without verification (to show value of symbolic layer)

### Evaluation
- Automatic metrics: BLEU, SARI, entity preservation
- Human evaluation: Fluency, adequacy, safety (1-5 scale)

## 🎓 Use Cases

### 1. Patient Portals
Hospitals can integrate SafeSim to automatically generate patient-friendly versions of:
- Discharge summaries
- Medication instructions
- Lab result explanations

### 2. Medical Education
Medical students can use SafeSim to:
- Learn medical terminology in context
- See how to communicate with patients
- Practice writing patient-friendly notes

### 3. Research
NLP researchers can use SafeSim as:
- A baseline for controllable generation
- A case study in neuro-symbolic AI
- A testbed for medical NLP

## ⚙️ Configuration

### LLM Backend Configuration

```python
# OpenAI
pipeline = SafeSimPipeline(
    llm_backend="openai",
    model="gpt-4o-mini",  # or "gpt-4"
    api_key="sk-..."
)

# Claude
pipeline = SafeSimPipeline(
    llm_backend="claude",
    model="claude-3-5-sonnet-20240620",
    api_key="sk-ant-..."
)

# HuggingFace
pipeline = SafeSimPipeline(
    llm_backend="huggingface",
    model_name="facebook/bart-large-cnn"
)

# Dummy (for testing)
pipeline = SafeSimPipeline(llm_backend="dummy")
```

### Strictness Levels

```python
# High strictness (recommended for clinical use)
pipeline = SafeSimPipeline(strictness="high")
# - All critical entities must match exactly
# - 95%+ similarity required
# - No missing dosages or medications allowed

# Medium strictness (balanced)
pipeline = SafeSimPipeline(strictness="medium")
# - Minor variations allowed
# - 85%+ similarity required
# - Max 1 missing non-critical entity

# Low strictness (research)
pipeline = SafeSimPipeline(strictness="low")
# - Semantic equivalence accepted
# - 75%+ similarity required
# - Max 2 missing non-critical entities
```

## 🛠️ Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_pipeline.py::TestEntityExtraction -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Adding New Entity Types

Edit `src/entity_extraction/extractor.py`:

```python
# Add new pattern
self.lab_value_pattern = re.compile(
    r'\b(?:HbA1c|Glucose|Creatinine)\s*[:=]?\s*\d+\.?\d*\b',
    re.IGNORECASE
)

# Add to extract() method
for match in self.lab_value_pattern.finditer(text):
    entities.append(MedicalEntity(
        text=match.group(),
        entity_type='LAB_VALUE',
        start_char=match.start(),
        end_char=match.end(),
        confidence=0.95
    ))
```

### Adding New LLM Backends

Edit `src/simplification/llm_simplifier.py`:

```python
class MyCustomSimplifier(LLMSimplifier):
    def __init__(self, **kwargs):
        super().__init__()
        # Initialize your model

    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        # Implement simplification
        pass
```

## 📝 Citation

If you use SafeSim in your research, please cite:

```bibtex
@inproceedings{safesim2024,
  title={SafeSim: Neuro-Symbolic Medical Text Simplification with Guaranteed Fact Preservation},
  author={Your Name},
  booktitle={NLP 607 Final Project},
  year={2024},
  institution={University of Maryland}
}
```

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **spaCy** for NER capabilities
- **Med-EASi dataset** creators (Basu et al.)
- **OpenAI, Anthropic, HuggingFace** for LLM APIs
- **Streamlit** for the web framework

## 📧 Contact

For questions or collaboration:
- Email: your.email@umd.edu
- GitHub Issues: [github.com/yourusername/safesim/issues](https://github.com/yourusername/safesim/issues)

---

**⚕️ Disclaimer**: SafeSim is a research prototype. Always consult healthcare professionals for medical advice. Do not use this system for actual patient care without proper clinical validation and regulatory approval.
