"""
Content Relevance Checker for SafeSim
Detects if input text is related to medical content before processing.
Critical for safety: prevents processing unrelated content as medical text.
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class RelevanceStatus(Enum):
    """Status of content relevance check"""
    MEDICAL = "medical"  # Clearly medical content
    LIKELY_MEDICAL = "likely_medical"  # Probably medical, but low confidence
    UNCLEAR = "unclear"  # Cannot determine
    UNRELATED = "unrelated"  # Clearly not medical content


@dataclass
class RelevanceResult:
    """Result of content relevance check"""
    status: RelevanceStatus
    is_relevant: bool  # True if should be processed, False if unrelated
    confidence: float  # 0.0 to 1.0
    medical_indicators: List[str]  # Found medical terms/patterns
    non_medical_indicators: List[str]  # Found non-medical terms/patterns
    explanation: str  # Human-readable explanation

    def to_dict(self):
        return {
            'status': self.status.value,
            'is_relevant': self.is_relevant,
            'confidence': self.confidence,
            'medical_indicators': self.medical_indicators,
            'non_medical_indicators': self.non_medical_indicators,
            'explanation': self.explanation
        }


class ContentRelevanceChecker:
    """
    Checks if input text is medical-related before processing.
    Uses pattern matching and heuristics to detect medical vs non-medical content.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the relevance checker.

        Args:
            strict_mode: If True, requires strong medical indicators. If False, more lenient.
        """
        self.strict_mode = strict_mode

        # Strong medical indicators (high confidence)
        self.strong_medical_patterns = [
            # Medications and dosages
            r'\b\d+\.?\d*\s*(?:mg|g|mcg|mL|L|units?|IU|tablets?|capsules?)\b',
            r'\b(?:prescribed|prescription|medication|medication|drug|dose|dosage)\b',
            
            # Medical procedures and conditions
            r'\b(?:patient|diagnosis|diagnosed|symptom|treatment|therapy|clinical|medical|hospital|physician|doctor|nurse)\b',
            r'\b(?:hypertension|diabetes|bradycardia|tachycardia|hypotension|seizure|syncope|edema|dyspnea|dysuria)\b',
            
            # Medical abbreviations
            r'\b(?:PO|IV|IM|SC|q\.?d\.?|b\.?i\.?d\.?|t\.?i\.?d\.?|q\.?i\.?d\.?|prn)\b',
            
            # Vital signs
            r'\b\d+/\d+\s*mmHg\b',  # Blood pressure
            r'\b\d+\.?\d*\s*°?[FC]\b',  # Temperature
            r'\b\d+\s*bpm\b',  # Heart rate
            
            # Common medications (sample)
            r'\b(?:atenolol|metformin|lisinopril|aspirin|warfarin|insulin|morphine|amoxicillin)\b',
        ]

        # Moderate medical indicators (medium confidence)
        self.moderate_medical_patterns = [
            r'\b(?:blood|heart|lung|liver|kidney|brain|muscle|bone|nerve|tissue|organ)\b',
            r'\b(?:pain|ache|fever|nausea|vomit|dizzy|weak|tired|fatigue|swollen|red|bleeding)\b',
            r'\b(?:test|exam|scan|x-ray|mri|ct|ultrasound|lab|laboratory|result)\b',
            r'\b(?:surgery|operation|procedure|injection|vaccine|antibiotic|antibiotic)\b',
        ]

        # Non-medical indicators (suggest content is NOT medical)
        self.non_medical_patterns = [
            # Cooking/food
            r'\b(?:recipe|cooking|bake|fry|ingredient|flour|sugar|salt|pepper|oven|stove|kitchen)\b',
            
            # Sports/entertainment
            r'\b(?:game|match|player|team|score|goal|tournament|championship|sport|football|basketball)\b',
            
            # Technology/computers
            r'\b(?:computer|software|programming|code|algorithm|database|server|network|internet|website)\b',
            
            # Business/finance
            r'\b(?:stock|market|investment|profit|revenue|business|company|corporate|finance|banking)\b',
            
            # News/politics
            r'\b(?:election|president|government|policy|law|legal|court|judge|lawyer|politics)\b',
            
            # Travel/tourism
            r'\b(?:travel|vacation|hotel|flight|airport|destination|tourist|sightseeing|beach|mountain)\b',
            
            # Education
            r'\b(?:homework|assignment|exam|test|grade|student|teacher|school|university|college|course)\b',
            
            # Shopping/retail
            r'\b(?:shopping|store|buy|purchase|price|discount|sale|cart|checkout|product|item)\b',
        ]

        # Compile patterns for efficiency
        self.strong_medical_regex = [re.compile(p, re.IGNORECASE) for p in self.strong_medical_patterns]
        self.moderate_medical_regex = [re.compile(p, re.IGNORECASE) for p in self.moderate_medical_patterns]
        self.non_medical_regex = [re.compile(p, re.IGNORECASE) for p in self.non_medical_patterns]

    def check(self, text: str) -> RelevanceResult:
        """
        Check if text is medical-related.

        Args:
            text: Input text to check

        Returns:
            RelevanceResult with status and explanation
        """
        text_lower = text.lower()
        medical_indicators = []
        non_medical_indicators = []

        # Count strong medical indicators
        strong_count = 0
        for pattern in self.strong_medical_regex:
            matches = pattern.findall(text)
            if matches:
                strong_count += len(matches)
                medical_indicators.extend([m if isinstance(m, str) else m.group() for m in matches[:3]])  # Limit to 3 examples

        # Count moderate medical indicators
        moderate_count = 0
        for pattern in self.moderate_medical_regex:
            matches = pattern.findall(text)
            if matches:
                moderate_count += len(matches)
                medical_indicators.extend([m if isinstance(m, str) else m.group() for m in matches[:2]])  # Limit to 2 examples

        # Count non-medical indicators
        non_medical_count = 0
        for pattern in self.non_medical_regex:
            matches = pattern.findall(text)
            if matches:
                non_medical_count += len(matches)
                non_medical_indicators.extend([m if isinstance(m, str) else m.group() for m in matches[:3]])  # Limit to 3 examples

        # Calculate scores
        # Strong indicators are worth 3 points, moderate 1 point
        medical_score = (strong_count * 3) + moderate_count
        non_medical_score = non_medical_count * 2  # Non-medical indicators are weighted higher

        # Determine relevance
        total_score = medical_score - non_medical_score
        text_length = len(text.split())

        # Normalize confidence (0.0 to 1.0)
        if text_length > 0:
            confidence = min(1.0, abs(total_score) / max(1, text_length * 0.5))
        else:
            confidence = 0.0

        # Determine status
        if non_medical_score > medical_score and non_medical_count >= 2:
            # Clear non-medical content
            status = RelevanceStatus.UNRELATED
            is_relevant = False
            explanation = (
                f"This text appears to be UNRELATED to medical content. "
                f"Found {non_medical_count} non-medical indicators (e.g., {', '.join(non_medical_indicators[:3])}) "
                f"but only {strong_count + moderate_count} medical indicators. "
                f"This system is designed ONLY for medical text simplification. "
                f"Processing unrelated content could produce misleading or incorrect results."
            )
        elif strong_count >= 2 or (strong_count >= 1 and moderate_count >= 2):
            # Clear medical content
            status = RelevanceStatus.MEDICAL
            is_relevant = True
            explanation = (
                f"✅ Medical content detected. Found {strong_count} strong medical indicators "
                f"(e.g., {', '.join(medical_indicators[:3])}). Safe to process."
            )
        elif strong_count >= 1 or moderate_count >= 3:
            # Likely medical
            status = RelevanceStatus.LIKELY_MEDICAL
            is_relevant = True
            explanation = (
                f"⚠️ Likely medical content. Found {strong_count} strong and {moderate_count} moderate indicators. "
                f"Proceeding with caution."
            )
        elif medical_score > 0:
            # Some medical indicators but weak
            status = RelevanceStatus.UNCLEAR
            is_relevant = not self.strict_mode  # Only process if not in strict mode
            explanation = (
                f"⚠️ Content relevance is UNCLEAR. Found limited medical indicators "
                f"({strong_count} strong, {moderate_count} moderate). "
                f"{'Processing with caution.' if is_relevant else 'Rejecting for safety (strict mode).'}"
            )
        else:
            # No clear indicators
            status = RelevanceStatus.UNRELATED
            is_relevant = False
            explanation = (
                f"No medical indicators found in this text. "
                f"This system is designed ONLY for medical text simplification. "
                f"Please provide medical discharge summaries, clinical notes, or medication instructions."
            )

        return RelevanceResult(
            status=status,
            is_relevant=is_relevant,
            confidence=confidence,
            medical_indicators=medical_indicators[:5],  # Limit to 5
            non_medical_indicators=non_medical_indicators[:5],  # Limit to 5
            explanation=explanation
        )

    def explain(self, result: RelevanceResult) -> str:
        """Generate human-readable explanation"""
        return result.explanation


if __name__ == "__main__":
    # Test the relevance checker
    checker = ContentRelevanceChecker(strict_mode=True)

    # Test cases
    test_cases = [
        "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia.",
        "Mix 2 cups of flour with 1 cup of sugar. Bake at 350°F for 30 minutes.",
        "The team won the championship game with a score of 3-2.",
        "Patient has diabetes and takes metformin daily.",
        "How to install Python on your computer?",
    ]

    print("=" * 70)
    print("CONTENT RELEVANCE CHECKER TEST")
    print("=" * 70)

    for i, text in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"Test Case {i}:")
        print(f"{'='*70}")
        print(f"Text: {text}\n")

        result = checker.check(text)
        print(f"Status: {result.status.value}")
        print(f"Relevant: {result.is_relevant}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"\nExplanation:\n{result.explanation}")

        if result.medical_indicators:
            print(f"\nMedical indicators found: {', '.join(result.medical_indicators[:5])}")
        if result.non_medical_indicators:
            print(f"Non-medical indicators found: {', '.join(result.non_medical_indicators[:5])}")
