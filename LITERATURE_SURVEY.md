# Literature Survey: Medical Text Simplification and Fact Preservation

## Overview

This document provides a comprehensive literature survey for the SafeSim project, organizing related work into categories and explaining how SafeSim differs from and builds upon existing approaches.

## 1. Medical Text Simplification Datasets

### 1.1 Med-EASi (Medical Evidence-based Annotated Simplification)

**Citation**: Basu et al., "Med-EASi: Finely Annotated Dataset and Models for Controllable Simplification of Medical Texts" (AAAI 2023)

**Description**:
- 4,000+ sentence pairs from medical literature
- Expert vs. Layman versions with fine-grained annotations
- Tags for "elaborations" (adding context) and "replacements" (jargon → simple terms)
- Includes medical specialties: cardiology, oncology, diabetes, etc.

**Relevance to SafeSim**:
- Primary dataset for training and evaluation
- Annotation schema aligns with our entity extraction (medications, dosages explicitly marked)
- Controllability aspect matches our verification approach

**Key Statistics**:
- 4,459 sentence pairs
- Average simplification length: 1.3x longer (elaboration)
- 78% contain medical jargon replacements

### 1.2 Cochrane/MultiSim Dataset

**Citation**: Van den Bercken et al., "NapSS: Paragraph-level Medical Text Simplification via Narrative Prompting and Sentence-wise Simplification" (EACL 2023)

**Description**:
- Medical abstracts from Cochrane systematic reviews
- Paragraph-level simplification (vs sentence-level)
- Focus on evidence-based medicine

**Relevance to SafeSim**:
- Good for testing on longer discharge summaries
- Different granularity (paragraph vs sentence) tests pipeline robustness

**Limitation**: Less emphasis on preserving specific numerical values (our focus)

### 1.3 PLABA Dataset

**Citation**: Devaraj et al., "Paragraph-level Medical Text Simplification" (EMNLP 2021)

**Description**:
- Paragraph-level abstract simplification
- Derived from PubMed abstracts
- 280K sentence pairs

**Relevance to SafeSim**:
- Large-scale training data
- Used to train BART-UL baseline

---

## 2. Baseline Approaches

### 2.1 BART with Unlikelihood Training (BART-UL)

**Citation**: Devaraj et al., "Paragraph-level Medical Text Simplification" (EMNLP 2021)

**Method**:
- Fine-tune BART on medical simplification
- Unlikelihood loss to punish jargon words
- Loss function: L = L_standard + λ * L_unlikelihood

**Strengths**:
- Achieves high readability scores (Flesch-Kincaid)
- Good at replacing jargon

**Weaknesses**:
- No explicit fact preservation mechanism
- Can omit critical numerical values
- Treats all jargon equally (medication names vs. general terms)

**Why SafeSim is Different**:
- We add a symbolic verification layer
- Hierarchical treatment of entities (dosages are immutable, some jargon can be kept)

**Experimental Comparison**:
- Use BART-UL as our primary neural baseline
- Compare entity preservation rates

### 2.2 Standard Seq2Seq Models (T5, Pegasus)

**Citations**:
- Raffel et al., "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer" (JMLR 2020)
- Zhang et al., "PEGASUS: Pre-training with Extracted Gap-sentences for Abstractive Summarization" (ICML 2020)

**Method**:
- Pre-trained seq2seq models fine-tuned on simplification
- Standard cross-entropy loss

**Weaknesses**:
- Designed for general text, not medical
- No domain-specific constraints
- Hallucination problems

**Why SafeSim is Different**:
- We can use T5/Pegasus as backend LLMs
- But we wrap them with symbolic verification

---

## 3. Fact Preservation and Hallucination Detection

### 3.1 Fact-Controlled Hallucination Detection

**Citation**: "Fact-Controlled Diagnosis of Hallucinations in Medical Text Summarization" (Interspeech 2025)

**Method**:
- Post-hoc hallucination detection
- Compare generated summary against source using NLI
- Classify: supported, contradicted, neutral

**Similarity to SafeSim**:
- Both focus on fact preservation
- Both use verification mechanisms

**Key Difference**:
- They **detect** hallucinations after generation (diagnosis)
- We **prevent/fix** them during generation (mitigation)
- Our verification is deterministic (symbolic) vs. learned (neural NLI)

**Advantage of SafeSim**:
- Interpretable: we can point to specific missing entities
- Actionable: we can retry with explicit constraints
- Deterministic: no false negatives from NLI model errors

### 3.2 Entity-Constrained Summarization

**Citation**: Huang et al., "Entity-level Factual Consistency of Abstractive Text Summarization" (ACL 2022)

**Method**:
- Extract entities from source
- Constrain decoder to include them
- Use entity embedding injection

**Similarity to SafeSim**:
- Entity-centric approach
- Both extract entities first

**Key Difference**:
- They focus on extractive/mixed summarization
- We focus on abstractive simplification
- They inject entities into decoder (soft constraint)
- We verify after generation (hard constraint)

---

## 4. Controllable Generation

### 4.1 TESLEA (Reinforcement Learning for Simplification)

**Citation**: "Medical Text Simplification Using Reinforcement Learning" (JMIR 2022)

**Method**:
- RL framework with reward = α * readability + β * adequacy
- Adequacy measured by BLEU against reference
- Policy gradient training

**Similarity to SafeSim**:
- Both aim for safe simplification
- Both balance simplicity and preservation

**Key Difference**:
- TESLEA uses soft, learned rewards (continuous optimization)
- SafeSim uses hard, symbolic constraints (discrete verification)
- TESLEA requires reward engineering
- SafeSim uses deterministic entity matching

**Advantage of SafeSim**:
- More interpretable (can explain exactly what's missing)
- No need to tune reward weights (α, β)
- Guaranteed preservation (not probabilistic)

**When TESLEA Might Be Better**:
- If training data is abundant
- If you want end-to-end differentiable system
- If preservation constraints are soft (not safety-critical)

### 4.2 Prompt-based Control with GPT-3

**Citation**: Brown et al., "Language Models are Few-Shot Learners" (NeurIPS 2020)

**Method**:
- In-context learning with carefully crafted prompts
- Few-shot examples showing desired behavior

**Similarity to SafeSim**:
- We also use LLM prompting (GPT-4, Claude)
- Both leverage instruction-following

**Key Difference**:
- Pure prompting has no guarantees
- SafeSim adds verification layer
- We can detect when prompting fails and retry

**Experimental Setup**:
- Use GPT-3.5/GPT-4 few-shot as baseline
- Compare against SafeSim with GPT-4 + verification

---

## 5. Neuro-Symbolic AI

### 5.1 Neuro-Symbolic Concept Learner

**Citation**: Mao et al., "The Neuro-Symbolic Concept Learner" (ICLR 2019)

**Relevance**:
- Paradigm of combining neural perception with symbolic reasoning
- Neural: extract concepts from raw input
- Symbolic: reason over extracted concepts

**How SafeSim Applies This**:
- Neural: LLM simplification
- Symbolic: entity extraction + verification
- Reasoning: check if entity sets match

### 5.2 Neural Theorem Provers

**Citation**: Rocktäschel & Riedel, "End-to-end Differentiable Proving" (NIPS 2017)

**Relevance**:
- Differentiable symbolic reasoning
- Can backpropagate through logic

**Why We Don't Use This**:
- Our verification is non-differentiable by design
- We want interpretability over end-to-end training
- Safety-critical domain requires hard constraints

---

## 6. Medical NLP and Named Entity Recognition

### 6.1 SciSpacy and Medical NER

**Citation**: Neumann et al., "ScispaCy: Fast and Robust Models for Biomedical Natural Language Processing" (BioNLP 2019)

**Method**:
- spaCy models trained on biomedical text
- Entity types: CHEMICAL, DISEASE, PROTEIN, etc.

**How SafeSim Uses This**:
- We use scispacy for medication/condition extraction
- Augment with regex for structured entities (dosages, vitals)

### 6.2 Clinical BERT

**Citation**: Alsentzer et al., "Publicly Available Clinical BERT Embeddings" (Clinical NLP 2019)

**Potential Enhancement**:
- Could use Clinical BERT embeddings for entity disambiguation
- Future work: semantic similarity of medication names

---

## 7. Evaluation Metrics for Simplification

### 7.1 Readability Metrics
- **Flesch-Kincaid Grade Level**: Standard readability
- **SARI**: System output Against References and against the Input
  - Rewards: keeping important words, deleting complex words, adding simple words

### 7.2 Fact Preservation Metrics
- **Entity Preservation Rate**: % of critical entities preserved (our metric)
- **BLEU/ROUGE**: Overlap with reference (inadequate for preservation)
- **BERTScore**: Semantic similarity (can miss critical differences)

**Why We Need Custom Metrics**:
- BLEU/ROUGE don't distinguish critical vs. non-critical words
- "50mg" vs "60mg" might have high BLEU but is medically wrong
- Our entity-based metrics address this

---

## 8. Our Contributions: How SafeSim is Novel

### 8.1 Neuro-Symbolic Validation Loop
**Novel Contribution**: First work to combine entity extraction + LLM simplification + symbolic verification in a closed loop

**Comparison Table**:

| Approach | Neural Component | Symbolic Component | Verification | Interpretable |
|----------|------------------|--------------------| -------------|---------------|
| BART-UL | ✅ BART + Unlikelihood | ❌ | ❌ | ❌ |
| TESLEA | ✅ RL-based | ❌ | Soft (reward) | ❌ |
| Hallucination Detection | ✅ NLI model | ❌ | ✅ (post-hoc) | Partial |
| **SafeSim** | ✅ LLM | ✅ Entity extraction | ✅ (in-loop) | ✅ |

### 8.2 Deterministic Fact Preservation
**Novel Contribution**: Guaranteed preservation of critical entities through deterministic matching

- Not probabilistic (like RL rewards)
- Not learned (like NLI verification)
- Directly interpretable: "Dosage '50mg' is missing"

### 8.3 Hybrid Entity Extraction
**Novel Contribution**: Combine spaCy NER with regex patterns for comprehensive coverage

- NER for context-dependent entities (medications)
- Regex for structured entities (dosages, vitals)
- Prioritization: dosages are immutable, jargon can be transformed

### 8.4 Acceptable Transformation Dictionary
**Novel Contribution**: Explicit dictionary of medically-approved simplifications

- "q.d." → "once a day" is acceptable
- "50mg" → anything else is NOT acceptable
- Encoded domain knowledge from medical experts

---

## 9. Future Work and Open Questions

### 9.1 End-to-End Training
- Can we make the verification layer differentiable?
- Train LLM to directly minimize verification violations
- Challenge: balancing interpretability vs. performance

### 9.2 Multi-Lingual Simplification
- Extend to Spanish, Chinese medical texts
- Do entity patterns transfer across languages?

### 9.3 User Studies
- Do patients actually understand the simplified text?
- Can they follow medication instructions correctly?
- Measure real-world impact on health outcomes

### 9.4 Integration with Med-EASi Fine-Tuning
- Fine-tune BART on Med-EASi with our entity annotations
- Compare fine-tuned + verification vs. GPT-4 + verification

---

## 10. Summary: Literature Map

```
Medical Text Simplification
├── Datasets
│   ├── Med-EASi (AAAI 2023) ← Primary dataset
│   ├── Cochrane/MultiSim (EACL 2023)
│   └── PLABA (EMNLP 2021)
│
├── Neural Approaches (No safety guarantees)
│   ├── BART-UL (EMNLP 2021) ← Main baseline
│   ├── T5/Pegasus (JMLR 2020, ICML 2020)
│   └── GPT-3 Few-Shot (NeurIPS 2020)
│
├── Fact Preservation (Post-hoc detection)
│   ├── Hallucination Detection (Interspeech 2025)
│   └── Entity Factual Consistency (ACL 2022)
│
├── Controllable Generation (Soft constraints)
│   └── TESLEA RL (JMIR 2022) ← Close comparison
│
└── SafeSim (Neuro-Symbolic, Hard constraints) ← Our work
    ├── Symbolic: Entity extraction + verification
    ├── Neural: LLM simplification
    └── Loop: Retry on verification failure
```

---

## References

1. Basu et al. "Med-EASi: Finely Annotated Dataset and Models for Controllable Simplification of Medical Texts" AAAI 2023
2. Devaraj et al. "Paragraph-level Medical Text Simplification" EMNLP 2021
3. Van den Bercken et al. "NapSS: Paragraph-level Medical Text Simplification" EACL 2023
4. "Fact-Controlled Diagnosis of Hallucinations in Medical Text Summarization" Interspeech 2025
5. "Medical Text Simplification Using Reinforcement Learning" JMIR 2022
6. Huang et al. "Entity-level Factual Consistency of Abstractive Text Summarization" ACL 2022
7. Raffel et al. "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer" JMLR 2020
8. Brown et al. "Language Models are Few-Shot Learners" NeurIPS 2020
9. Mao et al. "The Neuro-Symbolic Concept Learner" ICLR 2019
10. Neumann et al. "ScispaCy: Fast and Robust Models for Biomedical Natural Language Processing" BioNLP 2019

---

**Note**: This literature survey will be updated as new papers are published and as we conduct our experiments for comparison.
