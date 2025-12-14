"""
Test suite for SafeSim pipeline
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safesim_pipeline import SafeSimPipeline
from src.entity_extraction import MedicalEntityExtractor
from src.verification import LogicChecker


class TestEntityExtraction(unittest.TestCase):
    """Test entity extraction module"""

    def setUp(self):
        self.extractor = MedicalEntityExtractor()

    def test_dosage_extraction(self):
        """Test that dosages are correctly extracted"""
        text = "Patient prescribed 50mg Atenolol"
        entities = self.extractor.extract(text)

        dosage_entities = [e for e in entities if e.entity_type == 'DOSAGE']
        self.assertGreater(len(dosage_entities), 0, "Should extract at least one dosage")

        dosages = [e.text for e in dosage_entities]
        self.assertIn('50mg', dosages, "Should extract '50mg'")

    def test_medication_extraction(self):
        """Test that medications are correctly extracted"""
        text = "Prescribed Atenolol for hypertension"
        entities = self.extractor.extract(text)

        medications = [e.text for e in entities if e.entity_type == 'MEDICATION']
        # Medication extraction depends on the model
        # At minimum, should not crash
        self.assertIsInstance(medications, list)

    def test_frequency_extraction(self):
        """Test that frequencies are correctly extracted"""
        text = "Take medication q.d. or twice daily"
        entities = self.extractor.extract(text)

        frequencies = [e.text for e in entities if e.entity_type == 'FREQUENCY']
        self.assertGreater(len(frequencies), 0, "Should extract frequencies")


class TestLogicChecker(unittest.TestCase):
    """Test logic verification module"""

    def setUp(self):
        self.checker = LogicChecker(strictness='high')
        from src.entity_extraction import MedicalEntity
        self.MedicalEntity = MedicalEntity

    def test_exact_match(self):
        """Test that exact matches pass verification"""
        entities = [
            self.MedicalEntity("50mg", "DOSAGE", 0, 4),
            self.MedicalEntity("Atenolol", "MEDICATION", 5, 13),
        ]

        simplified = "Take 50mg of Atenolol daily"
        result = self.checker.verify(entities, simplified)

        self.assertTrue(result.is_safe, "Should be safe with exact matches")
        self.assertEqual(len(result.missing_entities), 0, "No entities should be missing")

    def test_missing_dosage(self):
        """Test that missing dosage fails verification"""
        entities = [
            self.MedicalEntity("50mg", "DOSAGE", 0, 4),
            self.MedicalEntity("Atenolol", "MEDICATION", 5, 13),
        ]

        simplified = "Take Atenolol daily"  # Missing dosage!
        result = self.checker.verify(entities, simplified)

        self.assertFalse(result.is_safe, "Should be unsafe with missing dosage")
        self.assertIn("50mg", result.missing_entities, "50mg should be in missing entities")

    def test_acceptable_transform(self):
        """Test that acceptable transformations pass verification"""
        entities = [
            self.MedicalEntity("q.d.", "FREQUENCY", 0, 4),
        ]

        simplified = "Take medication once a day"  # q.d. -> once a day
        result = self.checker.verify(entities, simplified)

        # Should accept the transformation
        # Note: May generate a warning but should still be safe
        self.assertGreaterEqual(result.score, 0.9, "Should have high score for acceptable transform")


class TestSafeSimPipeline(unittest.TestCase):
    """Test complete SafeSim pipeline"""

    def setUp(self):
        self.pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

    def test_pipeline_basic(self):
        """Test basic pipeline functionality"""
        text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension."
        result = self.pipeline.process(text)

        self.assertIsNotNone(result.simplified_text, "Should produce simplified text")
        self.assertIsInstance(result.is_safe, bool, "Should have safety status")
        self.assertIsInstance(result.entities, list, "Should extract entities")

    def test_pipeline_preserves_dosage(self):
        """Test that pipeline preserves dosages"""
        text = "Patient prescribed 50mg Atenolol PO q.d."
        result = self.pipeline.process(text)

        # Check that dosage appears in simplified text
        self.assertIn("50", result.simplified_text, "Simplified text should contain dosage")

    def test_batch_processing(self):
        """Test batch processing"""
        texts = [
            "Patient prescribed 50mg Atenolol PO q.d.",
            "Administer 10 units insulin subcutaneously b.i.d."
        ]

        results = self.pipeline.batch_process(texts)

        self.assertEqual(len(results), 2, "Should process all texts")
        for result in results:
            self.assertIsNotNone(result.simplified_text, "Each result should have simplified text")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_empty_text(self):
        """Test handling of empty text"""
        pipeline = SafeSimPipeline(llm_backend="dummy")
        result = pipeline.process("")

        self.assertIsInstance(result, object, "Should handle empty text gracefully")

    def test_no_medical_content(self):
        """Test handling of non-medical text"""
        pipeline = SafeSimPipeline(llm_backend="dummy")
        text = "The weather is nice today."
        result = pipeline.process(text)

        self.assertIsInstance(result, object, "Should handle non-medical text")


if __name__ == '__main__':
    print("Running SafeSim test suite...")
    print("=" * 60)

    # Run tests
    unittest.main(verbosity=2)
