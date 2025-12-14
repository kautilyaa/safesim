"""
Comprehensive Evaluation Metrics for Medical Text Simplification

Implements:
1. Safety metrics (entity preservation, hallucination)
2. Quality metrics (SARI, BLEU, BERTScore)
3. Readability metrics (Flesch-Kincaid, etc.)
"""

import re
import numpy as np
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter
from dataclasses import dataclass, asdict
import logging

# Import evaluation libraries
try:
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    from nltk.tokenize import word_tokenize
    import nltk
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
except:
    print("NLTK not available, some metrics will be disabled")

try:
    from rouge_score import rouge_scorer
except:
    print("ROUGE not available")

try:
    from bert_score import score as bert_score_fn
except:
    print("BERTScore not available")

try:
    import sacrebleu
except:
    print("SacreBLEU not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EvaluationResults:
    """Container for all evaluation metrics"""

    # Safety metrics
    entity_preservation_rate: float  # % of entities preserved
    dosage_preservation_rate: float  # % of dosages preserved
    hallucination_rate: float  # % of hallucinated entities

    # Quality metrics
    bleu_score: Optional[float] = None
    rouge_1: Optional[float] = None
    rouge_2: Optional[float] = None
    rouge_l: Optional[float] = None
    sari_score: Optional[float] = None
    bert_score_f1: Optional[float] = None

    # Readability metrics
    flesch_kincaid_grade: Optional[float] = None
    avg_word_length: Optional[float] = None
    avg_sentence_length: Optional[float] = None

    # Compression
    compression_ratio: Optional[float] = None

    def to_dict(self):
        return asdict(self)


class MedicalSimplificationEvaluator:
    """
    Comprehensive evaluator for medical text simplification.
    Measures both safety and quality.
    """

    def __init__(self):
        # Entity patterns (from extractor)
        self.dosage_pattern = re.compile(
            r'\b\d+\.?\d*\s*(?:mg|g|mcg|mL|L|tablets?|capsules?|units?|IU|drops?)\b',
            re.IGNORECASE
        )

        self.medication_keywords = {
            'atenolol', 'metformin', 'lisinopril', 'aspirin', 'warfarin',
            'metoprolol', 'amlodipine', 'simvastatin', 'levothyroxine',
            'omeprazole', 'albuterol', 'insulin', 'prednisone', 'ibuprofen'
        }

    def extract_entities(self, text: str) -> Dict[str, Set[str]]:
        """Extract entities for comparison"""
        text_lower = text.lower()

        # Extract dosages
        dosages = set(match.group().lower().replace(' ', '')
                     for match in self.dosage_pattern.finditer(text))

        # Extract medications (simple keyword matching)
        medications = set()
        for med in self.medication_keywords:
            if med in text_lower:
                medications.add(med)

        return {
            'dosages': dosages,
            'medications': medications,
            'all_entities': dosages | medications
        }

    def calculate_entity_preservation(
        self,
        original: str,
        simplified: str
    ) -> Tuple[float, float, float]:
        """
        Calculate entity preservation rates.

        Returns:
            (entity_preservation_rate, dosage_preservation_rate, hallucination_rate)
        """
        orig_entities = self.extract_entities(original)
        simp_entities = self.extract_entities(simplified)

        # Entity preservation rate
        if len(orig_entities['all_entities']) == 0:
            epr = 1.0
        else:
            preserved = len(orig_entities['all_entities'] & simp_entities['all_entities'])
            epr = preserved / len(orig_entities['all_entities'])

        # Dosage preservation rate
        if len(orig_entities['dosages']) == 0:
            dpr = 1.0
        else:
            preserved_dosages = len(orig_entities['dosages'] & simp_entities['dosages'])
            dpr = preserved_dosages / len(orig_entities['dosages'])

        # Hallucination rate
        if len(simp_entities['all_entities']) == 0:
            hr = 0.0
        else:
            hallucinated = len(simp_entities['all_entities'] - orig_entities['all_entities'])
            hr = hallucinated / len(simp_entities['all_entities'])

        return epr, dpr, hr

    def calculate_bleu(
        self,
        reference: str,
        hypothesis: str,
        weights: Tuple[float, ...] = (0.25, 0.25, 0.25, 0.25)
    ) -> float:
        """Calculate BLEU score"""
        try:
            ref_tokens = word_tokenize(reference.lower())
            hyp_tokens = word_tokenize(hypothesis.lower())

            smoothing = SmoothingFunction().method1
            score = sentence_bleu(
                [ref_tokens],
                hyp_tokens,
                weights=weights,
                smoothing_function=smoothing
            )
            return score
        except Exception as e:
            logger.warning(f"BLEU calculation failed: {e}")
            return 0.0

    def calculate_rouge(
        self,
        reference: str,
        hypothesis: str
    ) -> Dict[str, float]:
        """Calculate ROUGE scores"""
        try:
            scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
            scores = scorer.score(reference, hypothesis)

            return {
                'rouge1': scores['rouge1'].fmeasure,
                'rouge2': scores['rouge2'].fmeasure,
                'rougeL': scores['rougeL'].fmeasure,
            }
        except Exception as e:
            logger.warning(f"ROUGE calculation failed: {e}")
            return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}

    def calculate_sari(
        self,
        source: str,
        prediction: str,
        references: List[str]
    ) -> float:
        """
        Calculate SARI score.
        SARI = (F1_add + F1_keep + P_del) / 3
        """
        try:
            source_tokens = set(word_tokenize(source.lower()))
            pred_tokens = set(word_tokenize(prediction.lower()))
            ref_tokens_list = [set(word_tokenize(ref.lower())) for ref in references]

            # Words that were kept
            kept = pred_tokens & source_tokens
            # Words that were added
            added = pred_tokens - source_tokens
            # Words that were deleted
            deleted = source_tokens - pred_tokens

            # Calculate F1 for add and keep
            ref_added_union = set()
            ref_kept_union = set()
            for ref_tokens in ref_tokens_list:
                ref_added_union |= (ref_tokens - source_tokens)
                ref_kept_union |= (ref_tokens & source_tokens)

            # F1 for additions
            if len(added) == 0 and len(ref_added_union) == 0:
                f1_add = 1.0
            elif len(added) == 0 or len(ref_added_union) == 0:
                f1_add = 0.0
            else:
                precision_add = len(added & ref_added_union) / len(added)
                recall_add = len(added & ref_added_union) / len(ref_added_union)
                f1_add = 2 * precision_add * recall_add / (precision_add + recall_add + 1e-10)

            # F1 for keeping
            if len(kept) == 0 and len(ref_kept_union) == 0:
                f1_keep = 1.0
            elif len(kept) == 0 or len(ref_kept_union) == 0:
                f1_keep = 0.0
            else:
                precision_keep = len(kept & ref_kept_union) / len(kept)
                recall_keep = len(kept & ref_kept_union) / len(ref_kept_union)
                f1_keep = 2 * precision_keep * recall_keep / (precision_keep + recall_keep + 1e-10)

            # Precision for deletion (how much was deleted from reference)
            ref_deleted_union = set()
            for ref_tokens in ref_tokens_list:
                ref_deleted_union |= (source_tokens - ref_tokens)

            if len(deleted) == 0:
                p_del = 0.0
            else:
                p_del = len(deleted & ref_deleted_union) / len(deleted)

            sari = (f1_add + f1_keep + p_del) / 3
            return sari

        except Exception as e:
            logger.warning(f"SARI calculation failed: {e}")
            return 0.0

    def calculate_readability(self, text: str) -> Dict[str, float]:
        """Calculate readability metrics"""
        # Flesch-Kincaid Grade Level
        words = word_tokenize(text)
        sentences = text.split('.')

        # Count syllables (simple heuristic)
        def count_syllables(word):
            word = word.lower()
            count = 0
            vowels = 'aeiouy'
            previous_was_vowel = False
            for char in word:
                is_vowel = char in vowels
                if is_vowel and not previous_was_vowel:
                    count += 1
                previous_was_vowel = is_vowel
            if word.endswith('e'):
                count -= 1
            if count == 0:
                count = 1
            return count

        total_syllables = sum(count_syllables(w) for w in words)
        num_words = len(words)
        num_sentences = max(len(sentences), 1)

        # Flesch-Kincaid Grade Level
        if num_words == 0:
            fk_grade = 0
        else:
            fk_grade = (0.39 * (num_words / num_sentences) +
                       11.8 * (total_syllables / num_words) - 15.59)

        # Average word length
        avg_word_len = np.mean([len(w) for w in words]) if words else 0

        # Average sentence length
        avg_sent_len = num_words / num_sentences if num_sentences > 0 else 0

        return {
            'flesch_kincaid_grade': max(0, fk_grade),
            'avg_word_length': avg_word_len,
            'avg_sentence_length': avg_sent_len
        }

    def evaluate(
        self,
        original: str,
        simplified: str,
        reference: Optional[str] = None
    ) -> EvaluationResults:
        """
        Comprehensive evaluation of a single simplification.

        Args:
            original: Original medical text
            simplified: Simplified text
            reference: Reference simplification (optional, for SARI)

        Returns:
            EvaluationResults object
        """
        # Safety metrics
        epr, dpr, hr = self.calculate_entity_preservation(original, simplified)

        # Quality metrics (if reference provided)
        bleu = None
        rouge_scores = {'rouge1': None, 'rouge2': None, 'rougeL': None}
        sari = None

        if reference:
            bleu = self.calculate_bleu(reference, simplified)
            rouge_scores = self.calculate_rouge(reference, simplified)
            sari = self.calculate_sari(original, simplified, [reference])

        # Readability
        readability = self.calculate_readability(simplified)

        # Compression ratio
        compression = len(simplified) / len(original) if len(original) > 0 else 1.0

        return EvaluationResults(
            entity_preservation_rate=epr,
            dosage_preservation_rate=dpr,
            hallucination_rate=hr,
            bleu_score=bleu,
            rouge_1=rouge_scores['rouge1'],
            rouge_2=rouge_scores['rouge2'],
            rouge_l=rouge_scores['rougeL'],
            sari_score=sari,
            flesch_kincaid_grade=readability['flesch_kincaid_grade'],
            avg_word_length=readability['avg_word_length'],
            avg_sentence_length=readability['avg_sentence_length'],
            compression_ratio=compression
        )

    def batch_evaluate(
        self,
        originals: List[str],
        simplifieds: List[str],
        references: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Evaluate multiple examples and return average metrics.

        Returns:
            Dictionary of averaged metrics
        """
        results = []

        for i, (orig, simp) in enumerate(zip(originals, simplifieds)):
            ref = references[i] if references else None
            result = self.evaluate(orig, simp, ref)
            results.append(result)

        # Average all metrics
        avg_metrics = {}

        # Get all metric names
        sample_dict = results[0].to_dict()

        for key in sample_dict.keys():
            values = [r.to_dict()[key] for r in results if r.to_dict()[key] is not None]
            if values:
                avg_metrics[key] = np.mean(values)
            else:
                avg_metrics[key] = None

        return avg_metrics


if __name__ == "__main__":
    # Test evaluator
    evaluator = MedicalSimplificationEvaluator()

    original = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."
    simplified = "Take 50mg of Atenolol by mouth once a day for high blood pressure. Watch for slow heart rate."
    reference = "Take 50mg of Atenolol by mouth once daily for high blood pressure. Watch out for slow heart rate."

    results = evaluator.evaluate(original, simplified, reference)

    print("Evaluation Results:")
    print(f"Entity Preservation: {results.entity_preservation_rate:.2%}")
    print(f"Dosage Preservation: {results.dosage_preservation_rate:.2%}")
    print(f"Hallucination Rate: {results.hallucination_rate:.2%}")
    print(f"BLEU Score: {results.bleu_score:.3f}")
    print(f"SARI Score: {results.sari_score:.3f}")
    print(f"Flesch-Kincaid Grade: {results.flesch_kincaid_grade:.1f}")
