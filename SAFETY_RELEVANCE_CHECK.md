# Safety: Handling Unrelated Content

## Overview

SafeSim includes a **Content Relevance Checker** that detects whether input text is related to medical content before processing. This is a **critical safety feature** that prevents the system from processing unrelated content (e.g., cooking recipes, sports news, technology articles) as medical text, which could produce misleading or incorrect results.

## How It Works

### Stage 0: Content Relevance Check

Before any medical text processing begins, the system performs a relevance check:

1. **Pattern Matching**: The system scans for:
   - **Strong medical indicators**: Medications, dosages, medical procedures, vital signs, medical abbreviations
   - **Moderate medical indicators**: Body parts, symptoms, medical tests
   - **Non-medical indicators**: Cooking terms, sports, technology, business, etc.

2. **Scoring**: 
   - Medical indicators are weighted (strong = 3 points, moderate = 1 point)
   - Non-medical indicators are weighted (2 points each)
   - A relevance score is calculated

3. **Decision**:
   - **UNRELATED**: If non-medical indicators significantly outweigh medical indicators → **REJECT**
   - **MEDICAL**: If strong medical indicators are present → **PROCESS**
   - **LIKELY_MEDICAL**: If some medical indicators but uncertain → **PROCESS WITH CAUTION**
   - **UNCLEAR**: If very few indicators → **REJECT (strict mode) or PROCESS WITH CAUTION**

## Safety Behavior

### When Content is Unrelated

If the system detects unrelated content:

1. **Processing is STOPPED immediately** - No simplification is attempted
2. **Clear safety warning is displayed**:
   ```
   🚨 CRITICAL SAFETY ALERT: UNRELATED CONTENT
   
   This text appears to be UNRELATED to medical content.
   Found X non-medical indicators (e.g., flour, sugar, Bake) 
   but only Y medical indicators.
   
   This system is designed ONLY for medical text simplification.
   Processing unrelated content could produce misleading or incorrect results.
   ```
3. **Result fields**:
   - `is_relevant = False`
   - `is_safe = False`
   - `simplified_text = ""` (empty)
   - `warnings` contains detailed explanation

### When Content is Medical

If the system detects medical content:

1. **Processing continues normally** through all pipeline stages
2. **Relevance status is tracked** for transparency
3. **No warnings** unless verification fails

## Examples

### ✅ Medical Content (Processed)
```
Input: "Patient prescribed 50mg Atenolol PO q.d. for hypertension."
Status: MEDICAL
Result: Processed normally, simplified text generated
```

### ❌ Non-Medical Content (Rejected)
```
Input: "Mix 2 cups of flour with 1 cup of sugar. Bake at 350°F."
Status: UNRELATED
Result: 
- Processing stopped
- Safety alert displayed
- No simplified text generated
- Clear explanation provided
```

### ⚠️ Unclear Content (Rejected in Strict Mode)
```
Input: "The patient feels tired."
Status: UNCLEAR (if strict_mode=True)
Result: Rejected - insufficient medical indicators
```

## Implementation Details

### Files Modified

1. **`src/verification/content_relevance.py`** (NEW)
   - `ContentRelevanceChecker` class
   - Pattern matching for medical/non-medical indicators
   - Scoring and decision logic

2. **`src/safesim_pipeline.py`** (UPDATED)
   - Added Stage 0: Content relevance check
   - Early return if content is unrelated
   - Added `is_relevant`, `relevance_status`, `relevance_explanation` to `SafeSimResult`

3. **`src/ui/app.py`** (UPDATED)
   - Displays relevance warnings prominently
   - Shows safety alerts for unrelated content
   - Prevents display of simplified text for unrelated content

### Configuration

The relevance checker can be configured:

```python
from src.verification.content_relevance import ContentRelevanceChecker

# Strict mode (default): Rejects unclear content
checker = ContentRelevanceChecker(strict_mode=True)

# Lenient mode: Processes unclear content with caution
checker = ContentRelevanceChecker(strict_mode=False)
```

## Safety Guarantees

1. **No False Positives**: Unrelated content is never processed as medical text
2. **Clear Communication**: Users receive explicit warnings when content is unrelated
3. **Early Detection**: Relevance check happens before any LLM processing
4. **Transparency**: All decisions are explained with specific indicators found

## Why This Matters

Processing unrelated content as medical text could:
- Produce misleading simplifications
- Create false sense of medical accuracy
- Waste computational resources
- Potentially confuse users

The relevance checker ensures SafeSim **only processes medical content**, maintaining the integrity and safety of the system.
