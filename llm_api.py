# llm_api.py
# This file uses the Google Gemini API to check RDR conditions
# and find differentiating conditions.

import google.generativeai as genai
import os
import json
import logging
from typing import Optional

# --- 1. Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Constants ---
MODEL_NAME = 'gemini-2.5-flash'
CHECK_PROMPT_FILE = 'prompt_template.txt'
DIFF_PROMPT_FILE = 'prompt_differentiate.txt'

# --- 2. Setup: Get API Key and load model ---
try:
    api_key = os.environ["API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    logging.error("API_KEY environment variable not set.")
    raise EnvironmentError("API_KEY environment variable not set.")

try:
    model = genai.GenerativeModel(MODEL_NAME)
    logging.info(f"Gemini model '{MODEL_NAME}' loaded successfully.")
except Exception as e:
    logging.error(f"Could not load Gemini model: {e}")
    raise

# --- 3. Load Prompt Templates ---
try:
    with open(CHECK_PROMPT_FILE, "r") as f:
        CHECK_PROMPT_TEMPLATE = f.read()
    logging.info(f"Loaded check prompt from {CHECK_PROMPT_FILE}")
    
    with open(DIFF_PROMPT_FILE, "r") as f:
        DIFF_PROMPT_TEMPLATE = f.read()
    logging.info(f"Loaded differentiate prompt from {DIFF_PROMPT_FILE}")
        
except FileNotFoundError as e:
    logging.error(f"Could not find prompt file: {e.filename}.")
    raise
except Exception as e:
    logging.error(f"Error reading prompt file: {e}")
    raise

# --- 4. Main API Functions ---

def llm_check_condition(transcript_json_path: str, condition_string: str) -> bool:
    """
    (Function 1)
    Reads a JSON transcript, sends it to the Gemini API with a condition,
    and returns True or False.
    """
    try:
        with open(transcript_json_path, "r") as f:
            transcript_data = json.load(f)
        transcript_content = json.dumps(transcript_data, indent=2)
    except Exception as e:
        logging.error(f"llm_api(check): Error reading file {transcript_json_path}: {e}")
        return False

    # Formulate the prompt
    prompt = CHECK_PROMPT_TEMPLATE.format(
        transcript_content=transcript_content,
        condition_string=condition_string
    )

    try:
        response = model.generate_content(prompt)
        text_response = response.text.strip().upper().replace(".", "")
        logging.info(f"LLM Check: (Condition: '{condition_string}') -> (Response: '{text_response}')")
    
        if text_response == 'TRUE':
            return True
        elif text_response == 'FALSE':
            return False
        else:
            logging.warning(f"LLM(check) gave non-boolean answer: '{response.text}'")
            return False
    except Exception as e:
        logging.error(f"LLM(check) API call failed: {e}")
        return False

def llm_get_differentiating_conditions(transcript_json_path_NEW: str, transcript_json_path_OLD: Optional[str]) -> list[str]:
    """
    (Function 2 - UPDATED)
    Compares a new transcript against an old transcript file and returns a
    list of differentiating conditions.
    """
    # 1. Load the NEW transcript (mandatory)
    try:
        with open(transcript_json_path_NEW, "r") as f:
            transcript_data_NEW = json.load(f)
        transcript_content_NEW = json.dumps(transcript_data_NEW, indent=2)
    except Exception as e:
        logging.error(f"llm_api(diff): Error reading NEW file {transcript_json_path_NEW}: {e}")
        return [] # Return empty list on failure

    # 2. Load the OLD transcript (optional)
    transcript_content_OLD = "None" # Default string for the prompt
    if transcript_json_path_OLD:
        try:
            with open(transcript_json_path_OLD, "r") as f:
                transcript_data_OLD = json.load(f)
            transcript_content_OLD = json.dumps(transcript_data_OLD, indent=2)
            logging.info(f"Comparing against old transcript: {transcript_json_path_OLD}")
        except FileNotFoundError:
            logging.warning(f"llm_api(diff): Old transcript file not found: {transcript_json_path_OLD}. Comparing against 'None'.")
        except Exception as e:
            logging.warning(f"llm_api(diff): Error reading OLD file {transcript_json_path_OLD}: {e}. Comparing against 'None'.")

    # 3. Formulate the prompt
    prompt = DIFF_PROMPT_TEMPLATE.format(
        transcript_content_NEW=transcript_content_NEW,
        transcript_content_OLD=transcript_content_OLD
    )
    
    logging.info("Calling LLM to find differentiating conditions...")

    # 4. Call API and parse response
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("`"):
            response_text = response_text[1:-1].strip()

        conditions_list = json.loads(response_text)
        
        if isinstance(conditions_list, list):
            logging.info(f"LLM(diff) found {len(conditions_list)} conditions.")
            return conditions_list
        else:
            logging.warning(f"LLM(diff) did not return a list. Got: {type(conditions_list)}")
            return []

    except json.JSONDecodeError:
        logging.warning(f"LLM(diff) gave invalid JSON: '{response.text}'")
        return []
    except Exception as e:
        logging.error(f"LLM(diff) API call failed: {e}")
        return []