"""
Entity Extraction Module for SafeSim
Extracts immutable medical entities (medications, dosages, vitals, etc.)
using Named Entity Recognition and pattern matching.
"""

import re
import sys
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
import spacy
from spacy.matcher import Matcher


@dataclass
class MedicalEntity:
    """Represents an extracted medical entity"""
    text: str
    entity_type: str  # 'MEDICATION', 'DOSAGE', 'FREQUENCY', 'VITAL', 'CONDITION'
    start_char: int
    end_char: int
    confidence: float = 1.0

    def to_dict(self):
        return {
            'text': self.text,
            'type': self.entity_type,
            'start': self.start_char,
            'end': self.end_char,
            'confidence': self.confidence
        }


class MedicalEntityExtractor:
    """
    Extracts critical medical entities that must be preserved during simplification.
    Uses a hybrid approach: spaCy NER + regex patterns for high-precision extraction.
    """

    def __init__(self, model_name: str = None):
        """
        Initialize the extractor.

        Args:
            model_name: spaCy model to use. If None, automatically selects:
                       - en_core_web_sm for Python 3.12+ (better compatibility)
                       - en_core_sci_md for Python < 3.12 (if available)
                       Falls back to en_core_web_sm if preferred model not available
        """
        # Auto-select model based on Python version for better compatibility
        if model_name is None:
            # Python 3.12+ has compatibility issues with older scispacy models
            if sys.version_info >= (3, 12):
                model_name = "en_core_web_sm"
            else:
                # Try scispacy model first for older Python versions
                model_name = "en_core_sci_md"
        
        # Try to load the requested model
        model_loaded = False
        if model_name == "en_core_sci_md":
            # Only try scispacy if explicitly requested or on older Python
            try:
                self.nlp = spacy.load(model_name)
                model_loaded = True
            except (OSError, ImportError):
                # Silently fall back - scispacy may not be compatible
                pass
        
        # Fall back to en_core_web_sm if model not loaded
        if not model_loaded:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Downloading en_core_web_sm...")
                import subprocess
                subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], 
                             check=False)
                self.nlp = spacy.load("en_core_web_sm")

        # Dosage pattern (e.g., "50mg", "2 tablets", "10 mL")
        self.dosage_pattern = re.compile(
            r'\b\d+\.?\d*\s*(?:mg|g|mcg|mL|L|tablets?|capsules?|units?|IU|drops?)\b',
            re.IGNORECASE
        )

        # Frequency pattern (e.g., "q.d.", "BID", "once daily", "every 6 hours")
        self.frequency_pattern = re.compile(
            r'\b(?:q\.?d\.?|b\.?i\.?d\.?|t\.?i\.?d\.?|q\.?i\.?d\.?|'
            r'once|twice|three times|four times)\s*(?:daily|a day|per day)?\b|'
            r'\bevery\s+\d+\s+(?:hours?|days?|weeks?)\b',
            re.IGNORECASE
        )

        # Vital signs pattern (e.g., "120/80 mmHg", "98.6°F", "72 bpm")
        self.vital_pattern = re.compile(
            r'\b\d+/\d+\s*mmHg\b|'  # Blood pressure
            r'\b\d+\.?\d*\s*°?[FC]\b|'  # Temperature
            r'\b\d+\s*bpm\b|'  # Heart rate
            r'\b\d+\.?\d*%\s*(?:O2|oxygen)\b',  # Oxygen saturation
            re.IGNORECASE
        )

        # Route of administration (e.g., "PO", "IV", "subcutaneous")
        self.route_pattern = re.compile(
            r'\b(?:PO|IV|IM|SC|subcut(?:aneous)?|oral(?:ly)?|intravenous(?:ly)?|'
            r'topical(?:ly)?|inhaled?)\b',
            re.IGNORECASE
        )

        # Common medication list (expandable)
        self.known_medications = {
            'atenolol', 'metformin', 'lisinopril', 'aspirin', 'warfarin',
            'metoprolol', 'amlodipine', 'simvastatin', 'levothyroxine',
            'omeprazole', 'albuterol', 'insulin', 'prednisone', 'ibuprofen',
            'desmopressin', 'morphine', 'amoxicillin', 'morphine'
        }

        # Common medical conditions/symptoms (for Med-EASi style text)
        self.known_conditions = {
            'hypertension', 'bradycardia', 'tachycardia', 'hypotension',
            'diabetes', 'obesity', 'obese', 'nocturia', 'dyspnea', 'dysuria',
            'hepatomegaly', 'splenomegaly', 'tachypnea', 'syncope', 'seizures',
            'delirium', 'coma', 'edema', 'glossitis', 'stomatitis', 'aphthous',
            'hyperemia', 'photophobia', 'lacrimation', 'sinusitis', 'hypothyroidism'
        }

        # Common anatomical terms
        self.known_anatomy = {
            'liver', 'kidney', 'heart', 'lung', 'brain', 'stomach', 'intestine',
            'bladder', 'prostate', 'thyroid', 'pancreas', 'spleen', 'adrenal'
        }

    def extract(self, text: str) -> List[MedicalEntity]:
        """
        Extract all medical entities from text.

        Args:
            text: Medical text to process

        Returns:
            List of MedicalEntity objects
        """
        entities = []

        # 1. Extract dosages (highest priority - these are immutable)
        for match in self.dosage_pattern.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(),
                entity_type='DOSAGE',
                start_char=match.start(),
                end_char=match.end(),
                confidence=1.0
            ))

        # 2. Extract frequencies
        for match in self.frequency_pattern.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(),
                entity_type='FREQUENCY',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.95
            ))

        # 3. Extract vital signs
        for match in self.vital_pattern.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(),
                entity_type='VITAL',
                start_char=match.start(),
                end_char=match.end(),
                confidence=1.0
            ))

        # 4. Extract routes of administration
        for match in self.route_pattern.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(),
                entity_type='ROUTE',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.9
            ))

        # 5. Use spaCy NER for medications and conditions
        doc = self.nlp(text)
        for ent in doc.ents:
            # Check if entity overlaps with already extracted entities
            if not self._overlaps_existing(ent.start_char, ent.end_char, entities):
                entity_type = self._map_spacy_label(ent.label_)
                if entity_type:
                    # Additional check for medications
                    if entity_type == 'MEDICATION':
                        if ent.text.lower() in self.known_medications or len(ent.text) > 4:
                            entities.append(MedicalEntity(
                                text=ent.text,
                                entity_type=entity_type,
                                start_char=ent.start_char,
                                end_char=ent.end_char,
                                confidence=0.85
                            ))
                    else:
                        entities.append(MedicalEntity(
                            text=ent.text,
                            entity_type=entity_type,
                            start_char=ent.start_char,
                            end_char=ent.end_char,
                            confidence=0.8
                        ))

        # 6. Fallback: Search for known medications even if spaCy didn't recognize them
        # This is important because spaCy's general model often misses medication names
        for med in self.known_medications:
            # Use word boundaries to find the medication name
            pattern = re.compile(r'\b' + re.escape(med) + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                # Check if this medication wasn't already extracted
                if not self._overlaps_existing(match.start(), match.end(), entities):
                    # Find the actual case in the text
                    actual_text = text[match.start():match.end()]
                    entities.append(MedicalEntity(
                        text=actual_text,
                        entity_type='MEDICATION',
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=0.8  # Slightly lower confidence since spaCy didn't find it
                    ))

        # 7. Extract known medical conditions/symptoms
        for condition in self.known_conditions:
            pattern = re.compile(r'\b' + re.escape(condition) + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._overlaps_existing(match.start(), match.end(), entities):
                    actual_text = text[match.start():match.end()]
                    entities.append(MedicalEntity(
                        text=actual_text,
                        entity_type='CONDITION',
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=0.75
                    ))

        # 8. Extract known anatomical terms
        for anatomy in self.known_anatomy:
            pattern = re.compile(r'\b' + re.escape(anatomy) + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._overlaps_existing(match.start(), match.end(), entities):
                    actual_text = text[match.start():match.end()]
                    entities.append(MedicalEntity(
                        text=actual_text,
                        entity_type='ANATOMY',
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=0.7
                    ))

        # 9. Extract capitalized medical terms (likely medications or proper medical terms)
        # This catches terms like "Desmopressin", "Atenolol", etc. that might be missed
        # Look for capitalized words that are likely medical terms
        for token in doc:
            # Check for capitalized words that look like medical terms
            # (capitalized, not at start of sentence, likely noun)
            if (token.is_upper or (token.text[0].isupper() and len(token.text) > 3)) and \
               token.pos_ in ['NOUN', 'PROPN'] and \
               token.text.lower() not in ['patient', 'patients', 'the', 'this', 'that', 'these', 'those']:
                # Check if it's not already extracted and looks medical
                if len(token.text) > 4 and token.text.isalpha():
                    # Check if it overlaps with existing entities
                    if not self._overlaps_existing(token.idx, token.idx + len(token.text), entities):
                        # Heuristic: if it's capitalized and looks like a medical term, extract it
                        # This will catch medications like "Desmopressin" that spaCy might miss
                        entities.append(MedicalEntity(
                            text=token.text,
                            entity_type='MEDICATION' if token.text[0].isupper() else 'CONDITION',
                            start_char=token.idx,
                            end_char=token.idx + len(token.text),
                            confidence=0.6  # Lower confidence for heuristic extraction
                        ))

        # Sort by start position
        entities.sort(key=lambda e: e.start_char)

        return entities

    def _overlaps_existing(self, start: int, end: int, entities: List[MedicalEntity]) -> bool:
        """Check if a span overlaps with already extracted entities"""
        for entity in entities:
            if not (end <= entity.start_char or start >= entity.end_char):
                return True
        return False

    def _map_spacy_label(self, label: str) -> str:
        """Map spaCy entity labels to our entity types"""
        mapping = {
            'CHEMICAL': 'MEDICATION',
            'DRUG': 'MEDICATION',
            'DISEASE': 'CONDITION',
            'SYMPTOM': 'CONDITION',
            'PERSON': None,  # Don't extract person names
            'GPE': None,
            'ORG': None,
        }
        return mapping.get(label, None)

    def get_entity_set(self, entities: List[MedicalEntity]) -> Set[str]:
        """
        Convert entities to a set of normalized strings for comparison.
        Useful for verification against simplified text.
        """
        return {e.text.lower().strip() for e in entities if e.entity_type in ['DOSAGE', 'MEDICATION', 'VITAL']}

    def highlight_entities(self, text: str, entities: List[MedicalEntity]) -> str:
        """
        Create a text representation with entity highlighting (for debugging).
        """
        result = []
        last_end = 0

        for entity in sorted(entities, key=lambda e: e.start_char):
            result.append(text[last_end:entity.start_char])
            result.append(f"[{entity.text}|{entity.entity_type}]")
            last_end = entity.end_char

        result.append(text[last_end:])
        return ''.join(result)


if __name__ == "__main__":
    # Test the extractor
    extractor = MedicalEntityExtractor()

    test_text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."

    print("Original text:", test_text)
    print("\nExtracting entities...")

    entities = extractor.extract(test_text)

    print(f"\nFound {len(entities)} entities:")
    for entity in entities:
        print(f"  - {entity.text:20} [{entity.entity_type:12}] (confidence: {entity.confidence:.2f})")

    print("\nHighlighted text:")
    print(extractor.highlight_entities(test_text, entities))
