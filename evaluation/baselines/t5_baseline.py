"""
T5 Baseline for Medical Text Simplification
"""

import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class T5Baseline:
    """
    T5 baseline for medical text simplification.
    Uses T5's text-to-text format.
    """

    def __init__(
        self,
        model_name: str = "t5-base",
        device: Optional[str] = None
    ):
        """
        Initialize T5 model.

        Args:
            model_name: T5 model variant ('t5-small', 't5-base', 't5-large')
            device: Device to run on
        """
        self.model_name = model_name

        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(f"Loading T5 model: {model_name} on {self.device}")

        self.tokenizer = T5Tokenizer.from_pretrained(model_name, legacy=False)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()

    def simplify(
        self,
        text: str,
        max_length: int = 128,
        min_length: int = 10,
        num_beams: int = 4,
        temperature: float = 1.0,
    ) -> str:
        """
        Simplify medical text using T5.

        Args:
            text: Input medical text
            max_length: Maximum output length
            min_length: Minimum output length
            num_beams: Number of beams for beam search
            temperature: Sampling temperature

        Returns:
            Simplified text
        """
        # T5 uses task prefixes
        input_text = f"simplify medical text: {text}"

        inputs = self.tokenizer(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding=True
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                inputs["input_ids"],
                max_length=max_length,
                min_length=min_length,
                num_beams=num_beams,
                temperature=temperature,
                early_stopping=True,
            )

        simplified = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return simplified.strip()

    def batch_simplify(
        self,
        texts: List[str],
        batch_size: int = 8,
        **kwargs
    ) -> List[str]:
        """Batch simplification"""
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = [self.simplify(text, **kwargs) for text in batch]
            results.extend(batch_results)

            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"Processed {i + len(batch)}/{len(texts)} texts")

        return results


if __name__ == "__main__":
    # Test T5 baseline
    t5 = T5Baseline(model_name="t5-small")

    test_text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."

    print("Original:", test_text)
    simplified = t5.simplify(test_text)
    print("Simplified:", simplified)
