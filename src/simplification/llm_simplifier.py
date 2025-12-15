"""
LLM-based Medical Text Simplification
Supports multiple LLM backends: OpenAI, Anthropic Claude, HuggingFace
"""

import os
import re
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SimplificationResult:
    """Result from LLM simplification"""
    original_text: str
    simplified_text: str
    model_used: str
    prompt_used: str
    success: bool = True
    error_message: Optional[str] = None


class LLMSimplifier(ABC):
    """Base class for LLM-based simplification"""

    def __init__(self):
        self.system_prompt = """You are a medical text simplification expert. Your task is to simplify complex medical discharge summaries and clinical notes into plain language that patients can understand.

CRITICAL RULES:
1. NEVER omit numerical values (dosages, vitals, measurements)
2. NEVER omit medication names
3. NEVER change the meaning of medical instructions
4. Replace medical jargon with simple terms (e.g., "hypertension" → "high blood pressure")
5. Explain abbreviations (e.g., "PO" → "by mouth", "q.d." → "once a day")
6. Keep all numbers EXACTLY as they appear
7. Maintain all safety-critical information

Output ONLY the simplified text, nothing else."""

    @abstractmethod
    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        """Simplify medical text"""
        pass

    def _build_prompt(self, text: str, entities: Optional[List] = None) -> str:
        """Build the user prompt with entity constraints"""
        prompt = f"Simplify this medical text:\n\n{text}"

        if entities:
            entity_list = ", ".join([f"'{e.text}'" for e in entities if e.entity_type in ['DOSAGE', 'MEDICATION', 'VITAL']])
            if entity_list:
                prompt += f"\n\nIMPORTANT: You MUST include these exact values in your simplified text: {entity_list}"

        return prompt


class OpenAISimplifier(LLMSimplifier):
    """Simplification using OpenAI GPT models"""

    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        super().__init__()
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        """Simplify using OpenAI API"""
        user_prompt = self._build_prompt(text, entities)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=500
            )

            simplified = response.choices[0].message.content.strip()

            return SimplificationResult(
                original_text=text,
                simplified_text=simplified,
                model_used=self.model,
                prompt_used=user_prompt,
                success=True
            )

        except Exception as e:
            return SimplificationResult(
                original_text=text,
                simplified_text="",
                model_used=self.model,
                prompt_used=user_prompt,
                success=False,
                error_message=str(e)
            )


class ClaudeSimplifier(LLMSimplifier):
    """Simplification using Anthropic Claude"""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: Optional[str] = None):
        super().__init__()
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable.")

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        """Simplify using Claude API"""
        user_prompt = self._build_prompt(text, entities)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.3,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            simplified = message.content[0].text.strip()

            return SimplificationResult(
                original_text=text,
                simplified_text=simplified,
                model_used=self.model,
                prompt_used=user_prompt,
                success=True
            )

        except Exception as e:
            return SimplificationResult(
                original_text=text,
                simplified_text="",
                model_used=self.model,
                prompt_used=user_prompt,
                success=False,
                error_message=str(e)
            )


class HuggingFaceSimplifier(LLMSimplifier):
    """Simplification using local HuggingFace models (e.g., BART, T5)"""

    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        super().__init__()
        self.model_name = model_name

        try:
            from transformers import pipeline
            self.pipe = pipeline("summarization", model=model_name)
        except ImportError:
            raise ImportError("transformers package not installed. Run: pip install transformers torch")

    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        """
        Simplify using HuggingFace model.
        Note: This is basic summarization. For better results, fine-tune on Med-EASi dataset.
        """
        try:
            # Add instruction prefix for better results
            input_text = f"Simplify for patients: {text}"

            result = self.pipe(
                input_text,
                max_length=150,
                min_length=30,
                do_sample=False
            )

            simplified = result[0]['summary_text']

            return SimplificationResult(
                original_text=text,
                simplified_text=simplified,
                model_used=self.model_name,
                prompt_used=input_text,
                success=True
            )

        except Exception as e:
            return SimplificationResult(
                original_text=text,
                simplified_text="",
                model_used=self.model_name,
                prompt_used=text,
                success=False,
                error_message=str(e)
            )


class DummySimplifier(LLMSimplifier):
    """
    Dummy simplifier for testing without API keys.
    Uses rule-based replacements with case-insensitive matching.
    """

    def __init__(self):
        super().__init__()
        import re
        
        # Expanded medical term replacements (case-insensitive)
        self.replacements = {
            # Cardiovascular terms
            'hypertension': 'high blood pressure',
            'bradycardia': 'slow heart rate',
            'tachycardia': 'fast heart rate',
            'hypotension': 'low blood pressure',
            'atrial fibrillation': 'irregular heartbeat',
            'myocardial infarction': 'heart attack',
            'congestive heart failure': 'heart failure',
            
            # Frequency abbreviations
            'q.d.': 'once a day',
            'q.d': 'once a day',
            'qd': 'once a day',
            'b.i.d.': 'twice a day',
            'b.i.d': 'twice a day',
            'bid': 'twice a day',
            't.i.d.': 'three times a day',
            't.i.d': 'three times a day',
            'tid': 'three times a day',
            'q.i.d.': 'four times a day',
            'q.i.d': 'four times a day',
            'qid': 'four times a day',
            'q4h': 'every 4 hours',
            'q6h': 'every 6 hours',
            'q8h': 'every 8 hours',
            'prn': 'as needed',
            
            # Routes of administration
            'PO': 'by mouth',
            'po': 'by mouth',
            'IV': 'into a vein',
            'iv': 'into a vein',
            'subcutaneous': 'under the skin',
            'subcutaneously': 'under the skin',
            'intramuscular': 'into a muscle',
            'intramuscularly': 'into a muscle',
            
            # Common medical terms
            'monitor for': 'watch out for',
            'monitor': 'watch',
            'prescribed': 'given',
            'administer': 'give',
            'dyspnea': 'shortness of breath',
            'dysuria': 'painful urination',
            'nocturia': 'frequent urination at night',
            'hepatomegaly': 'enlarged liver',
            'splenomegaly': 'enlarged spleen',
            'tachypnea': 'rapid breathing',
            'orthostatic hypotension': 'low blood pressure when standing',
            'glossitis': 'swollen tongue',
            'stomatitis': 'mouth sores',
            'aphthous ulcers': 'mouth ulcers',
            'conjunctival': 'eye',
            'hyperemia': 'redness',
            'photophobia': 'sensitivity to light',
            'lacrimation': 'tearing',
            'edema': 'swelling',
            'syncope': 'fainting',
            'seizures': 'convulsions',
            'delirium': 'confusion',
            'coma': 'unconsciousness',
            'neonate': 'newborn baby',
            'endotracheal': 'breathing tube',
            'meconium': 'first bowel movement',
            'aspirator': 'suction device',
            
            # Patient language
            'Patient ': 'You ',
            'patient ': 'you ',
            'The patient': 'You',
            'the patient': 'you',
        }
        
        # Compile regex patterns for case-insensitive word-boundary matching
        # Sort by length (longest first) to handle multi-word terms first
        sorted_replacements = sorted(self.replacements.items(), key=lambda x: len(x[0]), reverse=True)
        self.patterns = []
        for medical_term, simple_term in sorted_replacements:
            # Escape special regex characters
            escaped_term = re.escape(medical_term)
            # Use word boundaries for whole-word matching (case-insensitive)
            pattern = re.compile(r'\b' + escaped_term + r'\b', re.IGNORECASE)
            self.patterns.append((pattern, simple_term))

    def simplify(self, text: str, entities: Optional[List] = None) -> SimplificationResult:
        """Simple rule-based simplification with case-insensitive matching"""
        simplified = text
        
        # Apply replacements using regex patterns (case-insensitive, word-boundary aware)
        for pattern, replacement in self.patterns:
            simplified = pattern.sub(replacement, simplified)
        
        # Additional conversational improvements
        simplified = simplified.replace(" should be ", " should ")
        simplified = re.sub(r'\s+', ' ', simplified)  # Remove extra spaces
        
        return SimplificationResult(
            original_text=text,
            simplified_text=simplified.strip(),
            model_used="rule-based",
            prompt_used="N/A",
            success=True
        )


def get_simplifier(backend: str = "dummy", **kwargs) -> LLMSimplifier:
    """
    Factory function to get appropriate simplifier.

    Args:
        backend: One of 'openai', 'claude', 'huggingface', 'dummy'
        **kwargs: Additional arguments for the simplifier

    Returns:
        LLMSimplifier instance
    """
    backend = backend.lower()

    if backend == "openai":
        return OpenAISimplifier(**kwargs)
    elif backend == "claude":
        return ClaudeSimplifier(**kwargs)
    elif backend == "huggingface":
        return HuggingFaceSimplifier(**kwargs)
    elif backend == "dummy":
        return DummySimplifier()
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose from: openai, claude, huggingface, dummy")


if __name__ == "__main__":
    # Test with dummy simplifier
    simplifier = get_simplifier("dummy")

    test_text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."

    result = simplifier.simplify(test_text)

    print("Original:", result.original_text)
    print("Simplified:", result.simplified_text)
    print("Model:", result.model_used)
