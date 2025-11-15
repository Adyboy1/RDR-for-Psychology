# rdr_engine.py
# This file contains the main RDR model.
# It now stores file paths as cornerstone data.

import sys
import os
import pickle
import logging
import json  # <-- ADDED IMPORT
from typing import Optional, List, Tuple

# --- IMPORT FROM THE API FILE ---
from llm_api import llm_check_condition, llm_get_differentiating_conditions

# --- 1. Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
TREE_STORAGE_FILE = "rdr_tree.pkl"

# --- 2. Class Definitions ---

class Rule:
    """Represents: rule ::= if conditions then conclusions"""
    def __init__(self, conditions: str, conclusions: str):
        # 'conditions' is now a string representation of a JSON array
        self.conditions = conditions
        self.conclusions = conclusions

class Vertex:
    """Represents: vertex ::= rule data"""
    def __init__(self, rule: Rule, data: List[str]):
        self.rule = rule
        # data is a List of cornerstone case *file paths*
        self.data: List[str] = data 

class Node:
    """Represents: node ::= vertex tree tree"""
    def __init__(self, vertex: Vertex):
        self.vertex = vertex
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None

# --- 3. The RDR Engine ---

class RDREngine:
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
            
            condition = current_node.vertex.rule.conditions
            # llm_check_condition now receives a JSON array string
            is_true = llm_check_condition(transcript_json_path, condition)

            if is_true:
                last_true_node = current_node
                current_node = current_node.right
            else:
                current_node = current_node.left

        logging.info("--- Interpretation complete ---")
        return (last_tried_node, last_true_node)

    def revise(self, transcript_json_path: str):
        """
        Runs the Revise mode interactively.
        """
        logging.info(f"--- REVIEWING '{transcript_json_path}' ---")
        
        (n1, n2) = self.interpret(transcript_json_path)

        if n2:
            current_conclusion = n2.vertex.rule.conclusions
            logging.info(f"\nSystem's conclusion was: '{current_conclusion}'")
        else:
            current_conclusion = "No conclusion found (empty tree)."
            logging.info(f"\nSystem's conclusion was: {current_conclusion}")

        while True:
            answer = input("    Do you agree with this conclusion? (y/n): ").strip().lower()
            if answer in ('y', 'n'):
                break
            logging.warning("Please enter 'y' or 'n'.")
        
        clinician_agrees = (answer == 'y')

        if clinician_agrees:
            logging.info("Clinician AGREES. No revision needed.")
            if n2:
                # Ask to append this file path to the node's data
                file_answer = input(f"    Add '{transcript_json_path}' to this rule's data? (y/n): ").strip().lower()
                if file_answer == 'y':
                    n2.vertex.data.append(transcript_json_path)
                    logging.info(f"Appended file path to node: '{n2.vertex.rule.conditions}'")
            return # --- End of function ---

        # --- "FALSE" branch: Execute NEW revise section ---
        logging.info("Clinician DISAGREES. Starting revision...")
        
        print("\nPlease provide details for the new rule:")
        new_concl = input("    What is the CORRECT conclusion? > ")
        
        # Get cornerstone FILE PATH for comparison
        path_OLD: Optional[str] = None
        if n2 and n2.vertex.data:
            path_OLD = n2.vertex.data[0] # Compare against first cornerstone file path
            logging.info(f"\n    Comparing against old case file (s1): '{path_OLD}'")
        else:
            logging.info(f"\n    (Creating new root rule, no old case file to compare against.)")

        # --- NEW: Call LLM for differentiating conditions ---
        conditions_list = llm_get_differentiating_conditions(transcript_json_path, path_OLD)
        
        # --- [MODIFIED SECTION START] ---
        
        selected_conditions: List[str] = []
        
        if not conditions_list:
            logging.warning("LLM could not find differences. Reverting to manual input.")
            while True:
                manual_cond = input("    Enter a required condition (or press Enter when done): ").strip()
                if not manual_cond:
                    if not selected_conditions:
                        logging.warning("Please add at least one condition.")
                    else:
                        break # Done
                else:
                    if manual_cond not in selected_conditions:
                        selected_conditions.append(manual_cond)
                        logging.info(f"Added condition: '{manual_cond}'")
                    else:
                        logging.warning("Condition already added.")
        else:
            # --- NEW: Constrained input from list ---
            print("\n    The LLM found these potential conditions:")
            for i, cond in enumerate(conditions_list):
                print(f"      {i+1}. {cond}")
            
            while True:
                try:
                    print("\n    Current conditions:", json.dumps(selected_conditions))
                    choice_str = input(f"    Select condition(s) by number (e.g., '1, 3'), 'm' (manual), or 'd' (done): ").strip().lower()
                    
                    if choice_str == 'd':
                        if not selected_conditions:
                            logging.warning("No conditions selected. Please select at least one.")
                        else:
                            break # Done
                    
                    elif choice_str == 'm':
                        manual_cond = input("      Enter manual condition: ").strip()
                        if manual_cond:
                            if manual_cond not in selected_conditions:
                                selected_conditions.append(manual_cond)
                                logging.info(f"Added manual condition: '{manual_cond}'")
                            else:
                                logging.warning("Condition already added.")
                        else:
                            logging.warning("Empty condition ignored.")
                    
                    elif choice_str: # Not 'd' or 'm', so must be numbers
                        chosen_indices = [int(i.strip()) - 1 for i in choice_str.split(',')]
                        temp_add_list = []
                        
                        for idx in chosen_indices:
                            if not (0 <= idx < len(conditions_list)):
                                logging.warning(f"Invalid number: {idx + 1}. It will be ignored.")
                            else:
                                temp_add_list.append(conditions_list[idx])
                        
                        for cond in temp_add_list:
                            if cond not in selected_conditions:
                                selected_conditions.append(cond)
                                logging.info(f"Selected condition: '{cond}'")
                            else:
                                logging.warning(f"Condition '{cond}' already selected.")
                                
                except ValueError:
                    logging.warning("Invalid input. Please enter numbers (e.g., '1, 3'), 'm', or 'd'.")
        
        logging.info(f"Final set of {len(selected_conditions)} conditions selected.")

        # --- [MODIFIED SECTION END] ---

        # 6. Form new rule and node
        # The new node's cornerstone data is this transcript's file path
        
        # Convert the list of conditions into a single JSON string
        new_cond_string = json.dumps(selected_conditions, indent=2)

        new_rule = Rule(new_cond_string, new_concl)
        new_vertex = Vertex(new_rule, [transcript_json_path]) 
        new_node = Node(new_vertex)
        
        logging.info(f"\nCreated new node with rule: if {new_cond_string} then '{new_concl}'")
        logging.info(f"Set cornerstone case for new node to: '{transcript_json_path}'")

        # 7. Add new node to the tree
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
    try:
        with open(TREE_STORAGE_FILE, "wb") as f:
            pickle.dump(engine, f)
        logging.info(f"RDR tree saved to {TREE_STORAGE_FILE}")
    except Exception as e:
        logging.error(f"Could not save tree: {e}")

# --- 5. Main Interactive Loop ---

def main():
    engine = load_tree() 
    
    try:
        while True:
            print("\n" + "="*70)
            print("RDR Interactive Mode (LLM-Guided, File-Based)")
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
            
            # 2. Run the review process
            engine.revise(transcript_file) 
            
            # 3. Save the tree *after* every revision
            save_tree(engine)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Final save on exit
        save_tree(engine)
        print("Final tree state saved. Goodbye.")
        
if __name__ == "__main__":
    main()