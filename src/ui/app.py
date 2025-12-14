"""
SafeSim Streamlit Web Interface
Patient Portal for safe medical text simplification
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.safesim_pipeline import SafeSimPipeline
from src.entity_extraction import MedicalEntityExtractor

# Page configuration
st.set_page_config(
    page_title="SafeSim - Medical Text Simplification",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .safe-entity {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 3px;
        padding: 2px 5px;
        margin: 2px;
        display: inline-block;
    }
    .unsafe-warning {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .safe-badge {
        background-color: #28a745;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .unsafe-badge {
        background-color: #dc3545;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .entity-badge {
        display: inline-block;
        padding: 3px 8px;
        margin: 2px;
        border-radius: 3px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .entity-DOSAGE { background-color: #ff9999; color: white; }
    .entity-MEDICATION { background-color: #99ccff; color: white; }
    .entity-FREQUENCY { background-color: #ffcc99; color: white; }
    .entity-VITAL { background-color: #cc99ff; color: white; }
    .entity-ROUTE { background-color: #99ff99; color: white; }
    .entity-CONDITION { background-color: #ffff99; color: #333; }
    </style>
""", unsafe_allow_html=True)


def highlight_entities_html(text: str, entities: list) -> str:
    """Create HTML with highlighted entities"""
    if not entities:
        return text

    # Sort entities by start position (reversed for proper replacement)
    sorted_entities = sorted(entities, key=lambda e: e['start'], reverse=True)

    result = text
    for entity in sorted_entities:
        start = entity['start']
        end = entity['end']
        entity_text = entity['text']
        entity_type = entity['type']

        # Create highlighted span
        highlighted = f'<span class="entity-badge entity-{entity_type}" title="{entity_type}">{entity_text}</span>'

        result = result[:start] + highlighted + result[end:]

    return result


def main():
    # Header
    st.title("🏥 SafeSim: Safe Medical Text Simplification")
    st.markdown("""
    SafeSim uses a **neuro-symbolic approach** to simplify medical discharge summaries
    while guaranteeing the preservation of critical facts (medications, dosages, vitals).
    """)

    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")

    llm_backend = st.sidebar.selectbox(
        "LLM Backend",
        ["dummy", "openai", "claude", "huggingface"],
        help="Select the language model backend. 'dummy' uses rule-based simplification for testing without API keys."
    )

    strictness = st.sidebar.selectbox(
        "Verification Strictness",
        ["high", "medium", "low"],
        help="How strict should the safety verification be? High = all entities must be preserved exactly."
    )

    # API key inputs (if needed)
    api_key = None
    if llm_backend == "openai":
        api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    elif llm_backend == "claude":
        api_key = st.sidebar.text_input("Anthropic API Key", type="password")

    # Example texts
    st.sidebar.header("📝 Example Texts")
    examples = {
        "Example 1: Hypertension": "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia.",
        "Example 2: Diabetes": "Administer 10 units insulin subcutaneously b.i.d. before meals. Check blood glucose q.i.d. Target range 80-120 mg/dL.",
        "Example 3: Post-op": "Patient received 2mg Morphine IV q4h PRN for pain. Maintain SBP >90 mmHg. Monitor O2 sat, keep >92%.",
        "Example 4: Cardiac": "Start Metoprolol 25mg PO b.i.d. for atrial fibrillation. Hold if HR <60 bpm or SBP <100 mmHg.",
    }

    selected_example = st.sidebar.selectbox("Load Example", [""] + list(examples.keys()))

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("📄 Input: Medical Text")

        # Text input
        default_text = examples.get(selected_example, "")
        input_text = st.text_area(
            "Paste discharge summary or clinical note:",
            value=default_text,
            height=200,
            placeholder="Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia."
        )

        process_button = st.button("🔄 Simplify Text", type="primary", use_container_width=True)

    with col2:
        st.header("✨ Output: Simplified Text")

        if process_button and input_text:
            with st.spinner("Processing..."):
                try:
                    # Initialize pipeline
                    kwargs = {}
                    if api_key:
                        kwargs['api_key'] = api_key

                    pipeline = SafeSimPipeline(
                        llm_backend=llm_backend,
                        strictness=strictness,
                        **kwargs
                    )

                    # Process text
                    result = pipeline.process(input_text, verbose=False)

                    # Display simplified text
                    if result.is_safe:
                        st.markdown(f'<div class="safe-badge">✅ SAFE</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="unsafe-badge">⚠️ NEEDS REVIEW</div>', unsafe_allow_html=True)

                    st.markdown(f"**Verification Score:** {result.verification['score']:.0%}")

                    st.text_area(
                        "Simplified text:",
                        value=result.simplified_text,
                        height=200,
                        disabled=True
                    )

                    # Show warnings
                    if result.warnings:
                        st.markdown('<div class="unsafe-warning">', unsafe_allow_html=True)
                        st.markdown("### ⚠️ Safety Alerts")
                        for warning in result.warnings:
                            st.warning(warning)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # Detailed analysis in expander
                    with st.expander("🔍 Detailed Analysis", expanded=False):
                        st.subheader("Extracted Entities")

                        # Display entities
                        if result.entities:
                            entity_html = highlight_entities_html(input_text, result.entities)
                            st.markdown(entity_html, unsafe_allow_html=True)

                            st.markdown("**Entity List:**")
                            for entity in result.entities:
                                st.markdown(
                                    f'<span class="entity-badge entity-{entity["type"]}">{entity["text"]}</span> '
                                    f'<span style="color: #666;">({entity["type"]})</span>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.info("No critical entities detected.")

                        st.markdown("---")

                        st.subheader("Verification Details")
                        st.json(result.verification)

                        st.markdown("---")

                        st.subheader("Model Information")
                        st.write(f"**Backend:** {result.model_used}")
                        st.write(f"**Strictness:** {strictness}")

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.info("If using OpenAI or Claude, make sure you've entered a valid API key in the sidebar.")

        elif process_button:
            st.warning("Please enter some medical text to simplify.")

    # Footer with information
    st.markdown("---")

    with st.expander("ℹ️ About SafeSim"):
        st.markdown("""
        ### How SafeSim Works

        SafeSim uses a **neuro-symbolic pipeline** with three stages:

        1. **Entity Extraction (Symbolic):** Uses Named Entity Recognition and pattern matching to identify critical medical entities:
           - Dosages (e.g., "50mg")
           - Medications (e.g., "Atenolol")
           - Vital signs (e.g., "120/80 mmHg")
           - Frequencies (e.g., "q.d.", "twice daily")
           - Routes (e.g., "PO", "IV")

        2. **LLM Simplification (Neural):** Uses large language models to convert medical jargon into plain language:
           - "hypertension" → "high blood pressure"
           - "q.d." → "once a day"
           - "bradycardia" → "slow heart rate"

        3. **Logic Verification (Symbolic):** Deterministically checks that all critical entities are preserved:
           - ✅ Green = Verified and safe
           - ⚠️ Red = Missing critical information

        ### Why This Matters

        Traditional text simplification models can "hallucinate" or omit critical medical information.
        SafeSim's symbolic verification layer **guarantees** that critical facts are never lost during simplification.

        ### Literature Survey

        SafeSim builds on recent advances in medical NLP:

        **Datasets:**
        - Med-EASi (Basu et al., AAAI 2023) - Finely annotated medical text simplification
        - Cochrane/MultiSim - Paragraph-level simplification benchmarks

        **Baselines:**
        - BART-UL (Devaraj et al., EMNLP 2021) - Unlikelihood training
        - T5/Pegasus - Standard seq2seq models

        **Novel Approach:**
        - Neuro-symbolic validation loop
        - Deterministic fact preservation
        - Interpretable safety guarantees

        ### Citation

        If you use SafeSim in your research, please cite:

        ```
        @inproceedings{safesim2024,
          title={SafeSim: Neuro-Symbolic Medical Text Simplification with Guaranteed Fact Preservation},
          author={Your Name},
          booktitle={NLP 607 Final Project},
          year={2024}
        }
        ```
        """)

    with st.expander("🚀 Technical Details"):
        st.markdown("""
        ### Architecture

        - **Entity Extraction:** spaCy + regex patterns
        - **LLM Backends:** OpenAI GPT-4, Claude, HuggingFace T5/BART
        - **Verification:** Deterministic string matching + fuzzy matching
        - **Interface:** Streamlit web application

        ### Strictness Levels

        - **High:** All critical entities must match exactly (95%+ similarity)
        - **Medium:** Minor variations allowed (85%+ similarity)
        - **Low:** Semantic equivalence accepted (75%+ similarity)

        ### Safety Guarantees

        SafeSim will **never** mark a simplification as safe if:
        - Any dosage is missing or modified
        - Any medication name is omitted
        - Any vital sign measurement is changed

        This makes SafeSim suitable for real-world clinical applications where patient safety is paramount.
        """)


if __name__ == "__main__":
    main()
