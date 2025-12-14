"""
Comprehensive Evaluation Script
Compares SafeSim against all baselines on multiple metrics
"""

import sys
from pathlib import Path
import json
import pandas as pd
from typing import List, Dict
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safesim_pipeline import SafeSimPipeline
from evaluation.baselines.bart_baseline import BARTBaseline
from evaluation.baselines.t5_baseline import T5Baseline
from evaluation.metrics.evaluation_metrics import MedicalSimplificationEvaluator


class ComprehensiveEvaluator:
    """
    Runs SafeSim and all baselines, computes metrics, generates comparison tables.
    """

    def __init__(self, test_data_path: str):
        """
        Initialize evaluator with test data.

        Args:
            test_data_path: Path to JSON file with test examples
        """
        self.test_data_path = test_data_path
        self.evaluator = MedicalSimplificationEvaluator()
        self.results = {}

        # Load test data
        with open(test_data_path, 'r') as f:
            data = json.load(f)
            self.test_examples = data['examples']

        print(f"Loaded {len(self.test_examples)} test examples")

    def run_safesim(self, backend='dummy', strictness='high'):
        """Run SafeSim pipeline"""
        print(f"\n{'='*60}")
        print(f"Running SafeSim ({backend}, strictness={strictness})")
        print('='*60)

        pipeline = SafeSimPipeline(llm_backend=backend, strictness=strictness)

        simplified_texts = []
        is_safe_list = []
        scores = []

        for example in tqdm(self.test_examples, desc="SafeSim"):
            result = pipeline.process(example['original'], verbose=False)
            simplified_texts.append(result.simplified_text)
            is_safe_list.append(result.is_safe)
            scores.append(result.verification['score'])

        # Evaluate
        originals = [ex['original'] for ex in self.test_examples]
        references = [ex.get('expected_simplified') for ex in self.test_examples]

        metrics = self.evaluator.batch_evaluate(originals, simplified_texts, references)
        metrics['safety_rate'] = sum(is_safe_list) / len(is_safe_list)
        metrics['avg_verification_score'] = sum(scores) / len(scores)

        self.results[f'SafeSim-{backend}'] = {
            'metrics': metrics,
            'simplifications': simplified_texts,
            'safe': is_safe_list
        }

        return metrics

    def run_bart_baseline(self):
        """Run BART baseline"""
        print(f"\n{'='*60}")
        print("Running BART Baseline")
        print('='*60)

        try:
            bart = BARTBaseline()

            simplified_texts = []
            for example in tqdm(self.test_examples, desc="BART"):
                simplified = bart.simplify(example['original'])
                simplified_texts.append(simplified)

            # Evaluate
            originals = [ex['original'] for ex in self.test_examples]
            references = [ex.get('expected_simplified') for ex in self.test_examples]

            metrics = self.evaluator.batch_evaluate(originals, simplified_texts, references)

            self.results['BART'] = {
                'metrics': metrics,
                'simplifications': simplified_texts
            }

            return metrics

        except Exception as e:
            print(f"BART baseline failed: {e}")
            return None

    def run_t5_baseline(self):
        """Run T5 baseline"""
        print(f"\n{'='*60}")
        print("Running T5 Baseline")
        print('='*60)

        try:
            t5 = T5Baseline(model_name="t5-small")

            simplified_texts = []
            for example in tqdm(self.test_examples, desc="T5"):
                simplified = t5.simplify(example['original'])
                simplified_texts.append(simplified)

            # Evaluate
            originals = [ex['original'] for ex in self.test_examples]
            references = [ex.get('expected_simplified') for ex in self.test_examples]

            metrics = self.evaluator.batch_evaluate(originals, simplified_texts, references)

            self.results['T5'] = {
                'metrics': metrics,
                'simplifications': simplified_texts
            }

            return metrics

        except Exception as e:
            print(f"T5 baseline failed: {e}")
            return None

    def run_all_evaluations(self):
        """Run all models and generate comparison"""
        # SafeSim with dummy backend (no API key needed)
        self.run_safesim(backend='dummy', strictness='high')

        # Baselines
        self.run_bart_baseline()
        self.run_t5_baseline()

        # Generate comparison table
        self.generate_comparison_table()
        self.save_results()

    def generate_comparison_table(self):
        """Generate and print comparison table"""
        print(f"\n{'='*80}")
        print("RESULTS COMPARISON")
        print('='*80)

        # Prepare data for table
        rows = []

        for model_name, data in self.results.items():
            metrics = data['metrics']
            row = {'Model': model_name}
            row.update(metrics)
            rows.append(row)

        df = pd.DataFrame(rows)

        # Reorder columns for readability
        priority_cols = [
            'Model',
            'entity_preservation_rate',
            'dosage_preservation_rate',
            'hallucination_rate',
            'sari_score',
            'bleu_score',
            'flesch_kincaid_grade',
            'safety_rate'
        ]

        # Add columns that exist
        cols = [c for c in priority_cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in priority_cols]
        df = df[cols + other_cols]

        # Format percentages
        pct_cols = ['entity_preservation_rate', 'dosage_preservation_rate',
                   'hallucination_rate', 'safety_rate']

        for col in pct_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.1%}" if x is not None else "N/A")

        # Format scores
        score_cols = ['sari_score', 'bleu_score', 'rouge_1', 'rouge_2', 'rouge_l',
                     'flesch_kincaid_grade']

        for col in score_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.3f}" if x is not None else "N/A")

        print(df.to_string(index=False))
        print()

        # Save to CSV
        output_path = Path(__file__).parent / 'results' / 'comparison_table.csv'
        output_path.parent.mkdir(exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Table saved to: {output_path}")

        return df

    def save_results(self):
        """Save detailed results to JSON"""
        output_path = Path(__file__).parent / 'results' / 'detailed_results.json'

        # Convert to serializable format
        save_data = {}
        for model_name, data in self.results.items():
            save_data[model_name] = {
                'metrics': data['metrics'],
                'simplifications': data.get('simplifications', [])
            }

        with open(output_path, 'w') as f:
            json.dump(save_data, f, indent=2)

        print(f"Detailed results saved to: {output_path}")

    def generate_visualizations(self):
        """Generate comparison plots"""
        print("\nGenerating visualizations...")

        # Extract metrics for plotting
        models = list(self.results.keys())

        # Safety metrics comparison
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('SafeSim vs Baselines: Comprehensive Evaluation', fontsize=16)

        # 1. Entity Preservation
        ax = axes[0, 0]
        epr_values = [self.results[m]['metrics']['entity_preservation_rate'] for m in models]
        ax.bar(models, epr_values, color=['#2ecc71', '#3498db', '#e74c3c'])
        ax.set_ylabel('Entity Preservation Rate')
        ax.set_title('Entity Preservation')
        ax.set_ylim([0, 1.1])
        for i, v in enumerate(epr_values):
            ax.text(i, v + 0.02, f'{v:.1%}', ha='center')

        # 2. Dosage Preservation
        ax = axes[0, 1]
        dpr_values = [self.results[m]['metrics']['dosage_preservation_rate'] for m in models]
        ax.bar(models, dpr_values, color=['#2ecc71', '#3498db', '#e74c3c'])
        ax.set_ylabel('Dosage Preservation Rate')
        ax.set_title('Dosage Preservation (Critical)')
        ax.set_ylim([0, 1.1])
        for i, v in enumerate(dpr_values):
            ax.text(i, v + 0.02, f'{v:.1%}', ha='center')

        # 3. SARI Score (if available)
        ax = axes[1, 0]
        sari_values = [self.results[m]['metrics'].get('sari_score', 0) or 0 for m in models]
        ax.bar(models, sari_values, color=['#2ecc71', '#3498db', '#e74c3c'])
        ax.set_ylabel('SARI Score')
        ax.set_title('Simplification Quality (SARI)')
        ax.set_ylim([0, 1.1])
        for i, v in enumerate(sari_values):
            if v > 0:
                ax.text(i, v + 0.02, f'{v:.3f}', ha='center')

        # 4. Flesch-Kincaid Grade
        ax = axes[1, 1]
        fk_values = [self.results[m]['metrics'].get('flesch_kincaid_grade', 0) or 0 for m in models]
        ax.bar(models, fk_values, color=['#2ecc71', '#3498db', '#e74c3c'])
        ax.set_ylabel('Grade Level')
        ax.set_title('Readability (Flesch-Kincaid)')
        for i, v in enumerate(fk_values):
            if v > 0:
                ax.text(i, v + 0.5, f'{v:.1f}', ha='center')

        plt.tight_layout()

        output_path = Path(__file__).parent / 'results' / 'comparison_plot.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to: {output_path}")

        plt.close()


def main():
    """Main evaluation entry point"""
    # Load test data
    test_data_path = Path(__file__).parent.parent / 'examples' / 'medical_texts.json'

    if not test_data_path.exists():
        print(f"Error: Test data not found at {test_data_path}")
        return

    evaluator = ComprehensiveEvaluator(str(test_data_path))

    print("="*80)
    print("COMPREHENSIVE EVALUATION: SAFESIM VS BASELINES")
    print("="*80)
    print(f"Test examples: {len(evaluator.test_examples)}")
    print()

    # Run all evaluations
    evaluator.run_all_evaluations()

    # Generate visualizations
    try:
        evaluator.generate_visualizations()
    except Exception as e:
        print(f"Visualization failed: {e}")

    print("\n" + "="*80)
    print("EVALUATION COMPLETE")
    print("="*80)
    print(f"Results saved to: evaluation/results/")


if __name__ == "__main__":
    main()
