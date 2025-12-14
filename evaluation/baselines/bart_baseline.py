"""
BART Baseline for Medical Text Simplification
Uses HuggingFace BART model for comparison
"""

import torch
from transformers import BartForConditionalGeneration, BartTokenizer
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BARTBaseline:
    """
    BART baseline for medical text simplification.
    Can be used with pretrained or fine-tuned models.
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-cnn",
        device: Optional[str] = None
    ):
        """
        Initialize BART model.

        Args:
            model_name: HuggingFace model name or path to fine-tuned model
            device: Device to run on ('cuda', 'mps', or 'cpu')
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

        logger.info(f"Loading BART model: {model_name} on {self.device}")

        self.tokenizer = BartTokenizer.from_pretrained(model_name)
        self.model = BartForConditionalGeneration.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()

    def simplify(
        self,
        text: str,
        max_length: int = 128,
        min_length: int = 10,
        num_beams: int = 4,
        length_penalty: float = 2.0,
        no_repeat_ngram_size: int = 3,
    ) -> str:
        """
        Simplify medical text using BART.

        Args:
            text: Input medical text
            max_length: Maximum output length
            min_length: Minimum output length
            num_beams: Number of beams for beam search
            length_penalty: Length penalty for generation
            no_repeat_ngram_size: Prevent repetition

        Returns:
            Simplified text
        """
        # Add instruction prefix for better results
        input_text = f"Simplify for patients: {text}"

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
                length_penalty=length_penalty,
                no_repeat_ngram_size=no_repeat_ngram_size,
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
        """
        Simplify multiple texts in batches.

        Args:
            texts: List of medical texts
            batch_size: Batch size for processing
            **kwargs: Additional arguments for simplify()

        Returns:
            List of simplified texts
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = [self.simplify(text, **kwargs) for text in batch]
            results.extend(batch_results)

            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"Processed {i + len(batch)}/{len(texts)} texts")

        return results


if __name__ == "__main__":
    # Test BART baseline
    bart = BARTBaseline()

    test_text = "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."

    print("Original:", test_text)
    simplified = bart.simplify(test_text)
    print("Simplified:", simplified)
