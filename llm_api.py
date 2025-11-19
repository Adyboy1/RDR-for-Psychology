# llm_api.py
import google.generativeai as genai
import os
import json
import logging
from typing import Optional, List

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
MODEL_NAME = 'gemini-2.5-flash'

# Prompt Files
CHECK_PROMPT_FILE = 'prompt_template.txt'
DIFF_PROMPT_FILE = 'prompt_differentiate.txt'
SUMMARY_PROMPT_FILE = 'prompt_summary.txt' # New
MERGE_PROMPT_FILE = 'prompt_merge.txt'     # New

# --- Setup ---
try:
    api_key = os.environ["API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    raise EnvironmentError(f"Setup failed: {e}")

# --- Load Prompts ---
def load_prompt(filename):
    try:
        with open(filename, "r") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error loading {filename}: {e}")
        return ""

CHECK_TEMPLATE = load_prompt(CHECK_PROMPT_FILE)
DIFF_TEMPLATE = load_prompt(DIFF_PROMPT_FILE)
SUMMARY_TEMPLATE = load_prompt(SUMMARY_PROMPT_FILE)
MERGE_TEMPLATE = load_prompt(MERGE_PROMPT_FILE)

# --- Core Functions ---

def llm_generate_summary(transcript_path: str) -> str:
    """
    Reads raw JSON transcript and generates a Clinical Prototype Summary.
    """
    try:
        with open(transcript_path, "r") as f:
            raw_data = json.load(f)
        raw_text = json.dumps(raw_data, indent=2)
        
        prompt = SUMMARY_TEMPLATE.format(transcript_content=raw_text)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Summary generation failed: {e}")
        return ""

def llm_check_condition(summary_text: str, condition_string: str) -> bool:
    """
    Checks if a SUMMARY satisfies a condition.
    """
    prompt = CHECK_TEMPLATE.format(
        summary_content=summary_text, 
        condition_string=condition_string
    )
    try:
        response = model.generate_content(prompt)
        logging.info(f"LLM Check: '{condition_string}' -> {response.text.strip().upper()}")
        return 'TRUE' in response.text.strip().upper()
    except Exception:
        return False

def llm_merge_summaries(old_summary: str, new_summary: str) -> str:
    """
    Merges a new patient profile into an existing consolidated group profile.
    """
    prompt = MERGE_TEMPLATE.format(
        old_summary=old_summary,
        new_summary=new_summary
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Merge failed: {e}")
        return old_summary # Fallback: keep old summary

def llm_get_differentiating_conditions(new_summary: str, ref_summary: str) -> List[str]:
    """
    Compares NEW summary vs REFERENCE summary to find differences.
    """
    prompt = DIFF_TEMPLATE.format(
        summary_new=new_summary,
        summary_ref=ref_summary if ref_summary else "None"
    )
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0]
        
        return json.loads(text)
    except Exception as e:
        logging.error(f"Diff extraction failed: {e}")
        return []