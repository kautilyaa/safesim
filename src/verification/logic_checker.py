"""
Neuro-Symbolic Logic Checker for SafeSim
Verifies that critical medical entities are preserved in simplified text.
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import re
from difflib import SequenceMatcher


@dataclass
class VerificationResult:
    """Result of verification check"""
    is_safe: bool
    missing_entities: List[str]
    modified_entities: List[Tuple[str, str]]  # (original, simplified)
    warnings: List[str]
    score: float  # 0.0 to 1.0

    def to_dict(self):
        return {
            'is_safe': self.is_safe,
            'missing_entities': self.missing_entities,
            'modified_entities': self.modified_entities,
            'warnings': self.warnings,
            'score': self.score
        }


class LogicChecker:
    """
    Symbolic verification layer that ensures critical facts are preserved.
    Uses deterministic checks rather than learned patterns.
    """

    def __init__(self, strictness: str = "high"):
        """
        Initialize the logic checker.

        Args:
            strictness: 'high', 'medium', or 'low'
                       - high: All critical entities must match exactly
                       - medium: Minor variations allowed (e.g., spacing)
                       - low: Semantic equivalence accepted
        """
        self.strictness = strictness

        # Thresholds for different strictness levels
        self.thresholds = {
            'high': {'similarity': 0.95, 'missing_allowed': 0},
            'medium': {'similarity': 0.85, 'missing_allowed': 1},
            'low': {'similarity': 0.75, 'missing_allowed': 2}
        }

        # Acceptable transformations (e.g., abbreviation expansions)
        self.acceptable_transforms = {
            'q.d.': ['once a day', 'once daily', 'every day', 'daily'],
            'b.i.d.': ['twice a day', 'twice daily', 'two times a day'],
            't.i.d.': ['three times a day', 'three times daily'],
            'q.i.d.': ['four times a day', 'four times daily'],
            'po': ['by mouth', 'orally', 'oral'],
            'iv': ['intravenous', 'into a vein', 'through a vein'],
            'sc': ['subcutaneous', 'under the skin'],
            'im': ['intramuscular', 'into muscle'],
        }

    def verify(self, original_entities: List, simplified_text: str) -> VerificationResult:
        """
        Verify that critical entities from original text are preserved.

        Args:
            original_entities: List of MedicalEntity objects from extraction
            simplified_text: The simplified text to verify

        Returns:
            VerificationResult with safety status and details
        """
        simplified_lower = simplified_text.lower()
        missing = []
        modified = []
        warnings = []

        # Critical entity types that MUST be preserved
        critical_types = {'DOSAGE', 'MEDICATION', 'VITAL'}

        # Track which entities are found
        found_count = 0
        critical_count = 0

        for entity in original_entities:
            if entity.entity_type not in critical_types:
                continue

            critical_count += 1
            entity_text = entity.text.lower().strip()

            # Check 1: Exact match
            if entity_text in simplified_lower:
                found_count += 1
                continue

            # Check 2: Normalized match (remove extra spaces, dots)
            normalized_entity = self._normalize(entity_text)
            normalized_simplified = self._normalize(simplified_lower)

            if normalized_entity in normalized_simplified:
                found_count += 1
                continue

            # Check 3: Check for acceptable transformations
            if self._is_acceptable_transform(entity_text, simplified_lower):
                found_count += 1
                warnings.append(
                    f"Entity '{entity.text}' was transformed (acceptable for {entity.entity_type})"
                )
                continue

            # Check 4: Fuzzy match for dosages (e.g., "50mg" vs "50 mg")
            if entity.entity_type == 'DOSAGE':
                if self._fuzzy_match_dosage(entity_text, simplified_lower):
                    found_count += 1
                    continue

            # Check 5: For medications, check if root word is present
            if entity.entity_type == 'MEDICATION':
                root = self._get_medication_root(entity_text)
                if root and root in simplified_lower:
                    found_count += 1
                    continue

            # Entity not found - this is a problem
            missing.append(entity.text)

        # Calculate safety score
        if critical_count == 0:
            score = 1.0
        else:
            score = found_count / critical_count

        # Determine if text is safe based on strictness
        threshold = self.thresholds[self.strictness]
        is_safe = (
            score >= threshold['similarity'] and
            len(missing) <= threshold['missing_allowed']
        )

        # Generate warnings for missing critical entities
        if missing:
            for entity in missing:
                warnings.append(
                    f"SAFETY ALERT: Critical entity '{entity}' not found in simplified text!"
                )

        return VerificationResult(
            is_safe=is_safe,
            missing_entities=missing,
            modified_entities=modified,
            warnings=warnings,
            score=score
        )

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove periods (for abbreviations)
        text = text.replace('.', '')
        # Remove common punctuation
        text = re.sub(r'[,;:]', '', text)
        return text.strip()

    def _is_acceptable_transform(self, original: str, simplified: str) -> bool:
        """Check if transformation is in acceptable list"""
        original_norm = self._normalize(original)

        if original_norm in self.acceptable_transforms:
            acceptable = self.acceptable_transforms[original_norm]
            for acceptable_form in acceptable:
                if acceptable_form in simplified:
                    return True

        return False

    def _fuzzy_match_dosage(self, dosage: str, text: str) -> bool:
        """
        Fuzzy matching for dosages to handle spacing variations.
        E.g., "50mg" should match "50 mg"
        """
        # Extract number and unit
        match = re.match(r'(\d+\.?\d*)\s*([a-z]+)', dosage, re.IGNORECASE)
        if not match:
            return False

        number, unit = match.groups()

        # Look for the number followed by optional space and unit
        pattern = rf'\b{re.escape(number)}\s*{re.escape(unit)}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _get_medication_root(self, medication: str) -> str:
        """
        Get root of medication name (remove common suffixes).
        E.g., "Atenolol" -> "atenolol"
        """
        # Simple root extraction - can be enhanced with medical ontologies
        root = medication.lower().strip()

        # Remove common suffixes
        suffixes = ['tablets', 'capsule', 'mg', 'mcg', 'ml']
        for suffix in suffixes:
            if root.endswith(suffix):
                root = root[:-len(suffix)].strip()

        return root if len(root) > 3 else None

    def verify_with_entities(
        self,
        original_entities: List,
        simplified_entities: List
    ) -> VerificationResult:
        """
        Advanced verification by comparing entity sets.
        This requires running extraction on both original and simplified text.
        """
        # Convert to sets for comparison
        original_critical = {
            e.text.lower().strip()
            for e in original_entities
            if e.entity_type in {'DOSAGE', 'MEDICATION', 'VITAL'}
        }

        simplified_critical = {
            e.text.lower().strip()
            for e in simplified_entities
            if e.entity_type in {'DOSAGE', 'MEDICATION', 'VITAL'}
        }

        # Find missing and modified
        missing = list(original_critical - simplified_critical)
        extra = list(simplified_critical - original_critical)

        # Calculate Jaccard similarity
        intersection = len(original_critical & simplified_critical)
        union = len(original_critical | simplified_critical)
        jaccard = intersection / union if union > 0 else 0.0

        warnings = []
        if missing:
            warnings.append(f"Missing entities: {', '.join(missing)}")
        if extra:
            warnings.append(f"Extra entities (hallucinations?): {', '.join(extra)}")

        is_safe = jaccard >= self.thresholds[self.strictness]['similarity']

        return VerificationResult(
            is_safe=is_safe,
            missing_entities=missing,
            modified_entities=[],
            warnings=warnings,
            score=jaccard
        )

    def explain_verification(self, result: VerificationResult) -> str:
        """Generate human-readable explanation of verification"""
        if result.is_safe:
            explanation = f"SAFE: Verification score: {result.score:.1%}\n"
            explanation += "All critical medical entities are preserved."
        else:
            explanation = f"UNSAFE: Verification score: {result.score:.1%}\n"
            explanation += "The simplified text has issues:\n"

            if result.missing_entities:
                explanation += f"\nMissing {len(result.missing_entities)} critical entities:\n"
                for entity in result.missing_entities:
                    explanation += f"  - {entity}\n"

        if result.warnings:
            explanation += "\nWarnings:\n"
            for warning in result.warnings:
                explanation += f"  {warning}\n"

        return explanation


if __name__ == "__main__":
    # Test the logic checker
    from src.entity_extraction import MedicalEntity

    checker = LogicChecker(strictness='high')

    # Simulate extracted entities
    entities = [
        MedicalEntity("50mg", "DOSAGE", 0, 4),
        MedicalEntity("Atenolol", "MEDICATION", 5, 13),
        MedicalEntity("q.d.", "FREQUENCY", 17, 21),
    ]

    # Good simplified text
    good_text = "Take 50mg of Atenolol by mouth once a day for high blood pressure."
    result = checker.verify(entities, good_text)
    print("Good text verification:")
    print(checker.explain_verification(result))

    # Bad simplified text (missing dosage)
    bad_text = "Take Atenolol once a day for high blood pressure."
    result = checker.verify(entities, bad_text)
    print("\nBad text verification:")
    print(checker.explain_verification(result))
