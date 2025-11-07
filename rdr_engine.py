# rdr_engine.py
# This file contains the main RDR model, now with persistence and
# interactive revision.

import sys
import os
import pickle
import logging
from typing import Optional, List, Tuple

# --- IMPORT FROM THE API FILE ---
from llm_api import llm_check_condition

# --- 1. Configuration ---

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Constants ---
TREE_STORAGE_FILE = "rdr_tree.pkl"

# --- 2. Class Definitions (Unchanged) ---

class Rule:
    """Represents: rule ::= if conditions then conclusions"""
    def __init__(self, conditions: str, conclusions: str):
        self.conditions = conditions
        self.conclusions = conclusions

class Vertex:
    """Represents: vertex ::= rule data"""
    def __init__(self, rule: Rule, data: List[str]):
        self.rule = rule
        self.data = data

class Node:
    """Represents: node ::= vertex tree tree"""
    def __init__(self, vertex: Vertex):
        self.vertex = vertex
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None

# --- 3. The RDR Engine (Modified) ---

class RDREngine:
    """
    Controls the 'interpret' and 'revise' modes for the RDR tree.
    """
    def __init__(self):
        self.root: Optional[Node] = None

    def interpret(self, transcript_json_path: str) -> Tuple[Optional[Node], Optional[Node]]:
        """
        Runs the Interpret mode.
        Returns: (last_tried_node, last_true_node)
        """
        logging.info(f"--- INTERPRETING '{transcript_json_path}'---")
        
        last_tried_node: Optional[Node] = None
        last_true_node: Optional[Node] = None
        current_node: Optional[Node] = self.root

        while current_node:
            last_tried_node = current_node
            
            # Here is the API call for each node's condition
            condition = current_node.vertex.rule.conditions
            is_true = llm_check_condition(transcript_json_path, condition)

            if is_true:
                # Rule is TRUE: store this node and go RIGHT (to check exceptions)
                last_true_node = current_node
                current_node = current_node.right
            else:
                # Rule is FALSE: go LEFT (to check alternatives)
                current_node = current_node.left

        logging.info("--- Interpretation complete ---")
        return (last_tried_node, last_true_node)

    def revise(self, transcript_json_path: str):
        """
        Runs the Revise mode interactively.
        The summary is now asked for *inside* this function, if needed.
        """
        logging.info(f"--- REVIEWING '{transcript_json_path}' ---")
        
        # 1. Run interpret (unchanged)
        (n1, n2) = self.interpret(transcript_json_path)

        # 2. Get the conclusion (unchanged)
        if n2:
            current_conclusion = n2.vertex.rule.conclusions
            logging.info(f"\nSystem's conclusion was: '{current_conclusion}'")
        else:
            current_conclusion = "No conclusion found (empty tree)."
            logging.info(f"\nSystem's conclusion was: {current_conclusion}")

        # 3. INTERACTIVE REVISION (unchanged)
        while True:
            answer = input("   Do you agree with this conclusion? (y/n): ").strip().lower()
            if answer in ('y', 'n'):
                break
            logging.warning("Please enter 'y' or 'n'.")
        
        clinician_agrees = (answer == 'y')

        # 4. Handle the human's decision
        if clinician_agrees:
            logging.info("Clinician AGREES. No revision needed.")
            if n2:
                summary_answer = input("   Add a 1-line summary to this rule's data? (y/n): ").strip().lower()
                if summary_answer == 'y':
                    summary_of_x = input("      Enter 1-line summary: ").strip()
                    if summary_of_x:
                        n2.vertex.data.append(summary_of_x)
                        logging.info(f"Updated cornerstone data for node: '{n2.vertex.rule.conditions}'")
            return # --- End of function ---

        # 5. "FALSE" branch: Execute revise section
        logging.info("Clinician DISAGREES. Starting revision...")
        
        print("\nPlease provide details for the new rule:")
        new_concl = input("   What is the CORRECT conclusion? > ")
        
        if n2:
            logging.info(f"\n   The failing rule was for cases like: {n2.vertex.data}")

        # This follows your prompt: "Let s2 be a summary of x."
        summary_of_x = ""
        while not summary_of_x:
            summary_of_x = input("   Enter the 1-line cornerstone summary (s2) for this new rule: ").strip()
            if not summary_of_x:
                logging.warning("Cornerstone summary cannot be empty.")
        
        logging.info(f"   This new case (s2) is summarized as: '{summary_of_x}'")
        new_cond = input(f"   What condition is TRUE for this new case (s2) but FALSE for the old ones (s1)? > ")

        # 6. Form new rule and node
        new_rule = Rule(new_cond, new_concl)
        # Store the summary as the new cornerstone case
        new_vertex = Vertex(new_rule, [summary_of_x]) # This line now works
        new_node = Node(new_vertex)
        logging.info(f"\nCreated new node with rule: if '{new_cond}' then '{new_concl}'")

        # 7. Add new node to the tree (unchanged)
        if self.root is None:
            self.root = new_node
            logging.info("Set new node as ROOT of the tree.")
        elif n1 == n2:
            logging.info(f"Attaching new node as RIGHT (exception) child of: '{n1.vertex.rule.conditions}'")
            n1.right = new_node
        else:
            logging.info(f"Attaching new node as LEFT (alternative) child of: '{n1.vertex.rule.conditions}'")
            n1.left = new_node

# --- 4. Persistence Functions ---

def load_tree() -> RDREngine:
    """
    Loads the RDR engine object from the pickle file.
    If no file is found, returns a new, empty engine.
    """
    if os.path.exists(TREE_STORAGE_FILE):
        try:
            with open(TREE_STORAGE_FILE, "rb") as f:
                engine = pickle.load(f)
            logging.info(f"Loaded existing RDR tree from {TREE_STORAGE_FILE}")
            return engine
        except Exception as e:
            logging.warning(f"Could not load tree: {e}. Starting new tree.")
    
    logging.info("No existing tree found. Starting new tree.")
    return RDREngine()

def save_tree(engine: RDREngine):
    """Saves the entire RDR engine object to the pickle file."""
    try:
        with open(TREE_STORAGE_FILE, "wb") as f:
            pickle.dump(engine, f)
        logging.info(f"RDR tree saved to {TREE_STORAGE_FILE}")
    except Exception as e:
        logging.error(f"Could not save tree: {e}")

# --- 5. Main Interactive Loop ---

def main():
    # Load the engine from the file (or create a new one)
    engine = load_tree() 
    
    try:
        while True:
            print("\n" + "="*70)
            print("RDR Interactive Mode")
            print("Enter 'q' or 'quit' at any time to exit.")
            print("="*70)

            # 1. Get transcript path
            transcript_file = input("Enter path to JSON transcript file: ").strip()
            if transcript_file.lower() in ('q', 'quit'):
                break

            # Check if file exists
            if not os.path.exists(transcript_file):
                logging.error(f"File not found: {transcript_file}. Please try again.")
                continue
                
            # --- CHANGE 4: Section 2 (Get cornerstone summary) is REMOVED ---

            # 3. Run the review process
            # --- CHANGE 5: 'summary' is no longer passed ---
            engine.revise(transcript_file) 
            
            # 4. Save the tree *after* every revision
            save_tree(engine)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Final save on exit
        save_tree(engine)
        print("Final tree state saved. Goodbye.")
        
if __name__ == "__main__":
    main()