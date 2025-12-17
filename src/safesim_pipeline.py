"""
SafeSim: Main Pipeline
Orchestrates entity extraction, LLM simplification, and verification.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json

from src.entity_extraction import MedicalEntityExtractor, MedicalEntity
from src.simplification import get_simplifier, SimplificationResult
from src.verification import LogicChecker, VerificationResult
from src.verification.content_relevance import ContentRelevanceChecker, RelevanceResult


@dataclass
class SafeSimResult:
    """Complete result from SafeSim pipeline"""
    original_text: str
    simplified_text: str
    entities: List[Dict]
    verification: Dict
    is_safe: bool
    warnings: List[str]
    model_used: str
    is_relevant: bool = True  # Whether content is medical-related
    relevance_status: str = "medical"  # Status from relevance check
    relevance_explanation: str = ""  # Explanation of relevance check

    def to_dict(self):
        result = asdict(self)
        return result

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)


class SafeSimPipeline:
    """
    Main SafeSim pipeline implementing the neuro-symbolic approach.

    Pipeline stages:
    1. Entity Extraction (Symbolic)
    2. LLM Simplification (Neural)
    3. Logic Verification (Symbolic)
    4. Optional: Re-generation if verification fails
    """

    def __init__(
        self,
        llm_backend: str = "dummy",
        strictness: str = "high",
        max_retries: int = 2,
        **llm_kwargs
    ):
        """
        Initialize the SafeSim pipeline.

        Args:
            llm_backend: LLM to use ('openai', 'claude', 'huggingface', 'dummy')
            strictness: Verification strictness ('high', 'medium', 'low')
            max_retries: Maximum retries if verification fails
            **llm_kwargs: Additional arguments for LLM (e.g., model, api_key)
        """
        self.extractor = MedicalEntityExtractor()
        self.simplifier = get_simplifier(llm_backend, **llm_kwargs)
        self.checker = LogicChecker(strictness=strictness)
        self.relevance_checker = ContentRelevanceChecker(strict_mode=True)
        self.max_retries = max_retries
        self.llm_backend = llm_backend

    def process(self, text: str, verbose: bool = False) -> SafeSimResult:
        """
        Process medical text through the complete pipeline.

        Args:
            text: Original medical text
            verbose: Print intermediate results

        Returns:
            SafeSimResult with all information
        """
        if verbose:
            print("=" * 60)
            print("SAFESIM PIPELINE")
            print("=" * 60)
            print(f"\nOriginal text:\n{text}\n")

        # Stage 0: Check content relevance (CRITICAL SAFETY CHECK)
        if verbose:
            print("\n[Stage 0] Checking content relevance...")

        relevance_result = self.relevance_checker.check(text)

        if verbose:
            print(relevance_result.explanation)

        # If content is unrelated, return early with safety warning
        if not relevance_result.is_relevant:
            return SafeSimResult(
                original_text=text,
                simplified_text="",
                entities=[],
                verification={},
                is_safe=False,
                warnings=[
                    f"🚨 CRITICAL SAFETY ALERT: {relevance_result.explanation}",
                    "This text was NOT processed because it is unrelated to medical content.",
                    "SafeSim is designed ONLY for medical text simplification.",
                    "Please provide medical discharge summaries, clinical notes, or medication instructions."
                ],
                model_used=self.llm_backend,
                is_relevant=False,
                relevance_status=relevance_result.status.value,
                relevance_explanation=relevance_result.explanation
            )

        # Stage 1: Extract entities
        if verbose:
            print("\n[Stage 1] Extracting entities...")

        entities = self.extractor.extract(text)

        if verbose:
            print(f"Found {len(entities)} entities:")
            for entity in entities:
                print(f"  - {entity.text:20} [{entity.entity_type}]")

        # Stage 2: Simplify with LLM
        if verbose:
            print(f"\n[Stage 2] Simplifying with {self.llm_backend}...")

        simplification_result = self.simplifier.simplify(text, entities)

        if not simplification_result.success:
            # Simplification failed
            return SafeSimResult(
                original_text=text,
                simplified_text="",
                entities=[e.to_dict() for e in entities],
                verification={},
                is_safe=False,
                warnings=[f"Simplification failed: {simplification_result.error_message}"],
                model_used=self.llm_backend,
                is_relevant=True,
                relevance_status=relevance_result.status.value,
                relevance_explanation=relevance_result.explanation
            )

        simplified_text = simplification_result.simplified_text

        if verbose:
            print(f"Simplified text:\n{simplified_text}\n")

        # Stage 3: Verify
        if verbose:
            print("[Stage 3] Verifying safety...")

        verification_result = self.checker.verify(entities, simplified_text)

        if verbose:
            print(self.checker.explain_verification(verification_result))

        # Stage 4: Retry if verification fails (optional)
        retry_count = 0
        while not verification_result.is_safe and retry_count < self.max_retries:
            retry_count += 1

            if verbose:
                print(f"\n[Stage 4] Verification failed. Retry {retry_count}/{self.max_retries}...")
                print("Missing entities:", verification_result.missing_entities)

            # Create more explicit prompt with missing entities
            retry_prompt = self._create_retry_prompt(
                text,
                entities,
                verification_result.missing_entities
            )

            if verbose:
                print("Enhanced prompt with missing entities...")

            # Re-simplify with explicit constraints
            simplification_result = self.simplifier.simplify(text, entities)
            simplified_text = simplification_result.simplified_text

            # Re-verify
            verification_result = self.checker.verify(entities, simplified_text)

            if verbose:
                print(self.checker.explain_verification(verification_result))

        # Prepare final result
        warnings = verification_result.warnings.copy()
        
        # Add relevance warning if status is not clearly medical
        if relevance_result.status.value != "medical":
            warnings.insert(0, f"⚠️ Relevance Note: {relevance_result.explanation}")

        return SafeSimResult(
            original_text=text,
            simplified_text=simplified_text,
            entities=[e.to_dict() for e in entities],
            verification=verification_result.to_dict(),
            is_safe=verification_result.is_safe,
            warnings=warnings,
            model_used=simplification_result.model_used,
            is_relevant=True,
            relevance_status=relevance_result.status.value,
            relevance_explanation=relevance_result.explanation
        )

    def _create_retry_prompt(
        self,
        text: str,
        entities: List[MedicalEntity],
        missing: List[str]
    ) -> str:
        """Create enhanced prompt for retry with missing entities highlighted"""
        entity_list = ", ".join([f"'{e}'" for e in missing])
        return (
            f"Simplify this medical text. "
            f"CRITICAL: You MUST include these exact terms: {entity_list}\n\n"
            f"{text}"
        )

    def batch_process(self, texts: List[str], verbose: bool = False) -> List[SafeSimResult]:
        """Process multiple texts"""
        results = []
        for i, text in enumerate(texts):
            if verbose:
                print(f"\n{'='*60}")
                print(f"Processing text {i+1}/{len(texts)}")
                print(f"{'='*60}")

            result = self.process(text, verbose=verbose)
            results.append(result)

        return results

    def get_statistics(self, results: List[SafeSimResult]) -> Dict:
        """Calculate statistics from batch processing"""
        total = len(results)
        safe = sum(1 for r in results if r.is_safe)
        avg_score = sum(r.verification['score'] for r in results) / total if total > 0 else 0

        return {
            'total_processed': total,
            'safe_simplifications': safe,
            'unsafe_simplifications': total - safe,
            'safety_rate': safe / total if total > 0 else 0,
            'average_verification_score': avg_score
        }


if __name__ == "__main__":
    # Example usage
    pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

    test_text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."

    result = pipeline.process(test_text, verbose=True)

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(f"\nOriginal:\n{result.original_text}")
    print(f"\nSimplified:\n{result.simplified_text}")
    print(f"\nSafe: {result.is_safe}")
    print(f"\nVerification Score: {result.verification['score']:.1%}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  {warning}")
