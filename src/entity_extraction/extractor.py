"""
Entity Extraction Module for SafeSim
Extracts immutable medical entities (medications, dosages, vitals, etc.)
using Named Entity Recognition and pattern matching.
"""

import re
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

    def __init__(self, model_name: str = "en_core_sci_md"):
        """
        Initialize the extractor.

        Args:
            model_name: spaCy model to use (default: scispacy medical model)
                       Falls back to en_core_web_sm if scispacy not available
        """
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            print(f"Model {model_name} not found. Falling back to en_core_web_sm")
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Downloading en_core_web_sm...")
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
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
            'omeprazole', 'albuterol', 'insulin', 'prednisone', 'ibuprofen'
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
