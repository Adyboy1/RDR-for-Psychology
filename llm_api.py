# llm_api.py
# This file uses the Google Gemini API to check RDR conditions.

import google.generativeai as genai
import os
import json
import logging

# --- 1. Configuration ---

# Set up basic logging
# This will print messages like: [INFO] Gemini model loaded successfully.
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Constants ---
# Updated model name as requested
MODEL_NAME = 'gemini-2.5-flash' 
SYSTEM_INSTRUCTION = """
You are a medical data analyst. Your task is to evaluate a condition based on a patient's transcript.
Respond with only the single word 'TRUE' if the condition is met, and only 'FALSE' if it is not.
"""

# --- 2. Setup: Get API Key and load model ---

# This code runs ONCE when the module is imported.
try:
    api_key = os.environ["API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    logging.error("API_KEY environment variable not set.")
    logging.error("Please set the API_KEY environment variable to use the Gemini API.")
    raise EnvironmentError("API_KEY environment variable not set.")

# Load the Gemini model
try:
    model = genai.GenerativeModel(MODEL_NAME)
    logging.info(f"Gemini model '{MODEL_NAME}' loaded successfully.")
except Exception as e:
    logging.error(f"Could not load Gemini model: {e}")
    # This is a fatal error for this module.
    raise

# --- 3. The RDR-compatible API function ---

def llm_check_condition(transcript_json_path: str, condition_string: str) -> bool:
    """
    Reads a JSON transcript, sends it to the Gemini API with a condition,
    and returns True or False.
    """
    
    # 3a. Read the JSON transcript file
    try:
        with open(transcript_json_path, "r") as f:
            transcript_data = json.load(f)
        # Convert the dictionary to a JSON string for the prompt
        transcript_content = json.dumps(transcript_data, indent=2)
    
    except FileNotFoundError:
        logging.error(f"llm_api: Could not find transcript file: {transcript_json_path}")
        return False # Fail safe
    except json.JSONDecodeError:
        logging.error(f"llm_api: Could not parse JSON from: {transcript_json_path}")
        return False # Fail safe
    except Exception as e:
        logging.error(f"llm_api: Error reading file {transcript_json_path}: {e}")
        return False

    # 3b. Formulate the precise prompt
    prompt = f"""{SYSTEM_INSTRUCTION}

    Here is the patient transcript in JSON format:
    json
    {transcript_content}
    Evaluate the following condition against the transcript: Condition: {condition_string} <--- THIS IS THE LINE """

    try:
    # Send the prompt to the generative model
        response = model.generate_content(prompt)
        
        # Clean the model's output (e.g., " TRUE ", "TRUE.")
        text_response = response.text.strip().upper().replace(".", "")
        
        logging.info(f"LLM Check: (Condition: '{condition_string}') -> (Response: '{text_response}')")
    
        if text_response == 'TRUE':
            return True
        elif text_response == 'FALSE':
            return False
        else:
            # The model didn't give a clear answer
            logging.warning(f"LLM gave non-boolean answer: '{response.text}'")
            return False # Fail safe

    except Exception as e:
        logging.error(f"LLM API call failed: {e}")
        return False # Fail safe