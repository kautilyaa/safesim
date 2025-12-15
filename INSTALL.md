# Installation Guide for SafeSim

This guide will walk you through setting up SafeSim on your machine.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for cloning)

## Step 1: Clone or Download the Repository

### Option A: Using Git
```bash
git clone https://github.com/yourusername/safesim.git
cd safesim
```

### Option B: Download ZIP
1. Download the ZIP file from GitHub
2. Extract it to your desired location
3. Open a terminal and navigate to the extracted folder

## Step 2: Create a Virtual Environment (Recommended)

### On macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### On Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Streamlit (web interface)
- spaCy (NLP processing)
- OpenAI, Anthropic, HuggingFace libraries (LLM backends)
- Testing frameworks

## Step 4: Download spaCy Model

SafeSim requires a spaCy language model. Download the standard English model:

```bash
python -m spacy download en_core_web_sm
```

### Optional: Install SciSpacy for Better Medical Entity Recognition

For improved performance on medical text (Python < 3.12 only):

```bash
pip install scispacy
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_md-0.5.3.tar.gz
```

**Note**: `en_core_sci_md` may not be compatible with Python 3.12+. SafeSim will automatically use `en_core_web_sm` on Python 3.12+, which provides good medical entity recognition through regex patterns and standard NER.

## Step 5: Configure API Keys (Optional)

If you want to use OpenAI GPT or Anthropic Claude:

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

**Note**: If you don't have API keys, you can still use SafeSim with the "dummy" backend for testing.

## Step 6: Verify Installation

Run the test suite to make sure everything is working:

```bash
python -m pytest tests/ -v
```

You should see all tests passing.

## Step 7: Launch SafeSim

### Web Interface (Recommended)

```bash
streamlit run src/ui/app.py
```

This will open SafeSim in your browser at http://localhost:8501

### Command Line Interface

```python
python -c "
from src.safesim_pipeline import SafeSimPipeline

pipeline = SafeSimPipeline(llm_backend='dummy')
text = 'Patient prescribed 50mg Atenolol PO q.d. for hypertension.'
result = pipeline.process(text, verbose=True)
print(f'\nSimplified: {result.simplified_text}')
print(f'Safe: {result.is_safe}')
"
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'spacy'"
**Solution**: Make sure you've activated your virtual environment and run `pip install -r requirements.txt`

### Issue: "Can't find model 'en_core_web_sm'"
**Solution**: Run `python -m spacy download en_core_web_sm`

### Issue: "OpenAI API key not found"
**Solution**: Either:
1. Add your API key to `.env` file, OR
2. Use the dummy backend: `SafeSimPipeline(llm_backend="dummy")`

### Issue: Import errors from src/
**Solution**: Make sure you're running commands from the project root directory

### Issue: Streamlit won't start
**Solution**: Try:
```bash
streamlit run src/ui/app.py --server.port 8502
```

## Platform-Specific Notes

### macOS
- If you get SSL certificate errors, run:
  ```bash
  /Applications/Python\ 3.x/Install\ Certificates.command
  ```

### Windows
- If you get encoding errors, make sure your terminal supports UTF-8
- Use Command Prompt or PowerShell, not Git Bash

### Linux
- You may need to install additional dependencies:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-dev build-essential
  ```

## Alternative: Using Docker (Advanced)

If you prefer Docker:

```bash
# Build the image
docker build -t safesim .

# Run the container
docker run -p 8501:8501 safesim
```

## Next Steps

1. Open the web interface at http://localhost:8501
2. Try the example texts in the sidebar
3. Configure your preferred LLM backend in the settings
4. Read the README.md for more details on usage and customization

## Getting Help

If you encounter issues:
1. Check the troubleshooting section above
2. Review the README.md
3. Open an issue on GitHub
4. Contact: your.email@umd.edu

## Uninstallation

To remove SafeSim:

1. Deactivate the virtual environment:
```bash
deactivate
```

2. Delete the project folder and virtual environment

That's it! You're ready to use SafeSim.
