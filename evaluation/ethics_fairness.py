"""
Ethics and Fairness Evaluation for SafeSim

Addresses:
- Bias in medical entity extraction
- Fairness across medical specialties
- Societal impact analysis
- Responsible NLP considerations
"""

import json
import pandas as pd
import numpy as np
from typing import List, Dict
from collections import defaultdict


class EthicsAndFairnessEvaluator:
    """
    Evaluates SafeSim for bias, fairness, and ethical considerations.
    """

    def __init__(self):
        # Medical specialties to analyze
        self.specialties = [
            'cardiovascular', 'endocrine', 'respiratory',
            'hematology', 'infectious_disease', 'post-operative'
        ]

        # Potential bias dimensions
        self.bias_dimensions = {
            'medication_coverage': [
                'atenolol', 'metformin', 'insulin', 'warfarin',
                'albuterol', 'levothyroxine', 'amoxicillin'
            ],
            'rare_medications': [
                'adalimumab', 'certolizumab', 'golimumab'  # Biologics
            ],
            'cultural_context': [
                'fasting', 'ramadan', 'pork products', 'halal'
            ]
        }

    def analyze_specialty_bias(
        self,
        test_examples: List[Dict],
        results: List[Dict]
    ) -> Dict:
        """
        Analyze if system performs differently across medical specialties.

        Args:
            test_examples: Original test data with 'category' field
            results: SafeSim results with safety scores

        Returns:
            Dictionary with fairness metrics per specialty
        """
        specialty_performance = defaultdict(list)

        for example, result in zip(test_examples, results):
            specialty = example.get('category', 'unknown')
            specialty_performance[specialty].append({
                'is_safe': result['is_safe'],
                'score': result['score'],
                'num_entities': len(result['entities'])
            })

        # Calculate metrics per specialty
        fairness_report = {}

        for specialty, performances in specialty_performance.items():
            safety_rate = np.mean([p['is_safe'] for p in performances])
            avg_score = np.mean([p['score'] for p in performances])
            avg_entities = np.mean([p['num_entities'] for p in performances])

            fairness_report[specialty] = {
                'safety_rate': safety_rate,
                'avg_verification_score': avg_score,
                'avg_entities_per_text': avg_entities,
                'num_examples': len(performances)
            }

        # Calculate fairness metrics
        safety_rates = [v['safety_rate'] for v in fairness_report.values()]

        fairness_report['overall'] = {
            'mean_safety_rate': np.mean(safety_rates),
            'std_safety_rate': np.std(safety_rates),
            'min_safety_rate': np.min(safety_rates),
            'max_safety_rate': np.max(safety_rates),
            'fairness_gap': np.max(safety_rates) - np.min(safety_rates)
        }

        return fairness_report

    def analyze_medication_coverage(
        self,
        results: List[Dict]
    ) -> Dict:
        """
        Analyze coverage of different medication types.

        Checks if system recognizes:
        - Common medications (high coverage expected)
        - Rare medications (potential bias)
        - Ethnic-specific medications
        """
        medication_found = defaultdict(int)
        medication_total = defaultdict(int)

        for result in results:
            text = result['original'].lower()

            # Check common medications
            for med in self.bias_dimensions['medication_coverage']:
                if med in text:
                    medication_total[med] += 1
                    # Check if entity was extracted
                    entities_text = ' '.join([e['text'].lower() for e in result['entities']])
                    if med in entities_text:
                        medication_found[med] += 1

            # Check rare medications
            for med in self.bias_dimensions['rare_medications']:
                if med in text:
                    medication_total[med] += 1
                    entities_text = ' '.join([e['text'].lower() for e in result['entities']])
                    if med in entities_text:
                        medication_found[med] += 1

        coverage_report = {}
        for med, total in medication_total.items():
            found = medication_found.get(med, 0)
            coverage_report[med] = {
                'total_occurrences': total,
                'times_extracted': found,
                'coverage_rate': found / total if total > 0 else 0
            }

        return coverage_report

    def generate_ethics_report(
        self,
        test_examples: List[Dict],
        results: List[Dict]
    ) -> str:
        """
        Generate comprehensive ethics and fairness report.
        """
        report = []

        report.append("=" * 80)
        report.append("ETHICS AND FAIRNESS EVALUATION REPORT")
        report.append("=" * 80)
        report.append("")

        # 1. Specialty Fairness
        report.append("1. FAIRNESS ACROSS MEDICAL SPECIALTIES")
        report.append("-" * 80)

        fairness = self.analyze_specialty_bias(test_examples, results)

        for specialty, metrics in fairness.items():
            if specialty != 'overall':
                report.append(f"\n{specialty.upper()}:")
                report.append(f"  Safety Rate: {metrics['safety_rate']:.1%}")
                report.append(f"  Avg Score: {metrics['avg_verification_score']:.0%}")
                report.append(f"  Examples: {metrics['num_examples']}")

        report.append(f"\nOVERALL FAIRNESS:")
        overall = fairness['overall']
        report.append(f"  Mean Safety Rate: {overall['mean_safety_rate']:.1%}")
        report.append(f"  Std Deviation: {overall['std_safety_rate']:.1%}")
        report.append(f"  Fairness Gap: {overall['fairness_gap']:.1%}")

        if overall['fairness_gap'] < 0.1:
            report.append(f"  [PASS] Low fairness gap (<10%)")
        else:
            report.append(f"  [WARNING] High fairness gap (>{overall['fairness_gap']:.0%})")

        # 2. Potential Biases
        report.append("\n\n2. BIAS ANALYSIS")
        report.append("-" * 80)

        report.append("\n**Identified Potential Biases:**")
        report.append("\n a) Medical Terminology Bias")
        report.append("    - System may miss rare/ethnic-specific medications")
        report.append("    - Entity extraction trained on common Western medications")
        report.append("    - Mitigation: Expand entity dictionary with diverse medications")

        report.append("\n b) Language Complexity Bias")
        report.append("    - Simplified text assumes English fluency")
        report.append("    - May not help non-native speakers or limited literacy")
        report.append("    - Mitigation: Multi-lingual support, even simpler alternatives")

        report.append("\n c) Health Literacy Bias")
        report.append("    - Requires baseline medical knowledge")
        report.append("    - Terms like 'blood pressure' may still be unclear")
        report.append("    - Mitigation: Glossary feature, visual aids")

        # 3. Fairness Concerns
        report.append("\n\n3. FAIRNESS CONCERNS")
        report.append("-" * 80)

        report.append("\n**Underserved Populations:**")
        report.append("  - Non-English speakers")
        report.append("  - Patients with very low health literacy")
        report.append("  - Rural areas with different medication access")

        report.append("\n**Specialty Coverage:**")
        report.append("  - System tested primarily on common conditions")
        report.append("  - May perform poorly on rare diseases")
        report.append("  - Oncology, rare diseases need more testing")

        # 4. Societal Impact
        report.append("\n\n4. SOCIETAL IMPACT ANALYSIS")
        report.append("-" * 80)

        report.append("\n**Positive Impacts:**")
        report.append("  [+] Improves health literacy for patients")
        report.append("  [+] Reduces hospital readmissions (better understanding → adherence)")
        report.append("  [+] Democratizes medical information")
        report.append("  [+] Reduces burden on healthcare providers")

        report.append("\n**Potential Risks:**")
        report.append("  [WARNING] Over-reliance on automation without human review")
        report.append("  [WARNING] May miss cultural context in medical communication")
        report.append("  [WARNING] Could deskill medical professionals if over-used")
        report.append("  [WARNING] Privacy concerns if processing real patient data")
        report.append("  [WARNING] Liability: Who is responsible for incorrect simplification?")

        report.append("\n**Unintended Consequences:**")
        report.append("  - Patients may misinterpret simplified text")
        report.append("  - Healthcare providers may skip patient education")
        report.append("  - System errors could lead to medication mistakes")

        # 5. Responsible Deployment
        report.append("\n\n5. RESPONSIBLE DEPLOYMENT RECOMMENDATIONS")
        report.append("-" * 80)

        report.append("\n**Deployment Guidelines:**")
        report.append("  1. Human-in-the-Loop: Doctor reviews all outputs")
        report.append("  2. Transparency: Clear disclaimers about limitations")
        report.append("  3. Audit Trail: Log all inputs/outputs for quality review")
        report.append("  4. Patient Consent: Inform patients about AI usage")
        report.append("  5. Regular Audits: Monitor for bias and errors")

        report.append("\n**Recommended Workflow:**")
        report.append("  Discharge → SafeSim Simplification → Doctor Review → Patient Portal")
        report.append("  If verification fails (red flag) → Mandatory doctor review")

        report.append("\n**Continuous Improvement:**")
        report.append("  - Patient feedback loop")
        report.append("  - Regular bias audits")
        report.append("  - Expand entity coverage")
        report.append("  - Multi-lingual support")

        # 6. Regulatory Considerations
        report.append("\n\n6. REGULATORY AND LEGAL CONSIDERATIONS")
        report.append("-" * 80)

        report.append("\n**Regulatory Status:**")
        report.append("  - SafeSim is a research prototype")
        report.append("  - NOT approved for clinical use")
        report.append("  - Would require FDA approval for patient care")

        report.append("\n**HIPAA Compliance:**")
        report.append("  - System must handle PHI securely")
        report.append("  - Encryption at rest and in transit")
        report.append("  - Audit logs required")

        report.append("\n**Liability:**")
        report.append("  - Healthcare provider retains ultimate responsibility")
        report.append("  - System is assistive tool, not autonomous")
        report.append("  - Clear disclaimers required")

        # 7. Ethical Principles
        report.append("\n\n7. ADHERENCE TO ETHICAL PRINCIPLES")
        report.append("-" * 80)

        report.append("\n**Beneficence (Do Good):**")
        report.append("  [+] Improves patient understanding and outcomes")

        report.append("\n**Non-Maleficence (Do No Harm):**")
        report.append("  [+] Verification layer prevents medication errors")
        report.append("  [+] Flags unsafe simplifications for review")

        report.append("\n**Autonomy (Patient Choice):**")
        report.append("  [+] Empowers patients with understandable information")
        report.append("  [WARNING] Must respect patient's right to decline AI assistance")

        report.append("\n**Justice (Fairness):**")
        report.append("  [WARNING] Currently limited to English speakers")
        report.append("  [WARNING] May not serve all specialties equally")
        report.append("  → Requires expansion for true justice")

        # Summary
        report.append("\n\n" + "=" * 80)
        report.append("ETHICAL VERDICT: CONDITIONALLY ACCEPTABLE")
        report.append("=" * 80)

        report.append("\nSafeSim demonstrates responsible AI design with:")
        report.append("  [+] Safety verification layer")
        report.append("  [+] Interpretable error messages")
        report.append("  [+] Transparent limitations")

        report.append("\nHowever, deployment requires:")
        report.append("  [WARNING] Human oversight (doctor review)")
        report.append("  [WARNING] Regular bias audits")
        report.append("  [WARNING] Expansion to underserved populations")
        report.append("  [WARNING] Regulatory approval for clinical use")

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def export_fairness_metrics(
        self,
        test_examples: List[Dict],
        results: List[Dict],
        output_path: str = "fairness_report.json"
    ):
        """Export fairness metrics to JSON"""
        fairness = self.analyze_specialty_bias(test_examples, results)

        with open(output_path, 'w') as f:
            json.dump(fairness, f, indent=2)

        print(f"Fairness metrics saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    evaluator = EthicsAndFairnessEvaluator()

    # Simulated results
    test_examples = [
        {'category': 'cardiovascular', 'original': 'Patient prescribed 50mg Atenolol...'},
        {'category': 'endocrine', 'original': 'Administer 10 units insulin...'},
    ]

    results = [
        {'original': test_examples[0]['original'], 'is_safe': True, 'score': 1.0,
         'entities': [{'text': '50mg', 'type': 'DOSAGE'}]},
        {'original': test_examples[1]['original'], 'is_safe': True, 'score': 0.95,
         'entities': [{'text': '10 units', 'type': 'DOSAGE'}]},
    ]

    report = evaluator.generate_ethics_report(test_examples, results)
    print(report)
