# rdr_engine.py
import sys
import os
import pickle
import logging
import json
from typing import Optional, List, Tuple

# Import updated API functions
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Now you can just import directly
try:
    from llm_api import (
        llm_check_condition, 
        llm_get_differentiating_conditions, 
        llm_generate_summary, 
        llm_merge_summaries
    )
except ImportError:
    # Fallback if running from root
    from app.llm_api import (
        llm_check_condition, 
        llm_get_differentiating_conditions, 
        llm_generate_summary, 
        llm_merge_summaries
    )
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
#Path configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(CURRENT_DIR, '..','storage')
TREE_STORAGE_FILE = os.path.join(STORAGE_DIR, "rdr_tree_summary.pkl")

class Rule:
    def __init__(self, conditions: str, conclusions: str):
        self.conditions = conditions
        self.conclusions = conclusions

class Vertex:
    def __init__(self, rule: Rule, summary: str):
        self.rule = rule
        # Stores the "Consolidated Group Profile" text, not file paths
        self.summary: str = summary 

class Node:
    def __init__(self, vertex: Vertex):
        self.vertex = vertex
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None

class RDREngine:
    def __init__(self):
        self.root: Optional[Node] = None

    def interpret(self, current_patient_summary: str) -> Tuple[Optional[Node], Optional[Node]]:
        """
        Traverses the tree using the generated SUMMARY.
        """
        last_tried_node: Optional[Node] = None
        last_true_node: Optional[Node] = None
        current_node: Optional[Node] = self.root

        while current_node:
            last_tried_node = current_node
            
            condition = current_node.vertex.rule.conditions
            # Check condition against the summary text
            is_true = llm_check_condition(current_patient_summary, condition)

            if is_true:
                last_true_node = current_node
                current_node = current_node.right
            else:
                current_node = current_node.left

        return (last_tried_node, last_true_node)

    def revise(self, transcript_path: str):
        logging.info(f"--- PROCESSING '{transcript_path}' ---")

        # 1. Generate Summary for the new patient
        print("Generating clinical summary from transcript...")
        new_patient_summary = llm_generate_summary(transcript_path)
        
        if not new_patient_summary:
            logging.error("Failed to generate summary. Aborting.")
            return

        # 2. Run Interpret
        (n1, n2) = self.interpret(new_patient_summary)

        if n2:
            current_conclusion = n2.vertex.rule.conclusions
            logging.info(f"\nSystem's conclusion: '{current_conclusion}'")
        else:
            current_conclusion = "No conclusion (empty tree)."
            logging.info(f"\nSystem's conclusion: {current_conclusion}")

        # 3. Interaction
        while True:
            answer = input("    Do you agree? (y/n): ").strip().lower()
            if answer in ('y', 'n'): break
        
        # --- AGREEMENT PATH (MERGE) ---
        if answer == 'y':
            logging.info("Clinician AGREES.")
            if n2:
                print("Merging new patient data into existing group profile...")
                # Merge logic [cite: 20-33]
                updated_summary = llm_merge_summaries(n2.vertex.summary, new_patient_summary)
                n2.vertex.summary = updated_summary
                logging.info("Group profile updated.")
            return

        # --- DISAGREEMENT PATH (DIFFERENTIATE) ---
        logging.info("Clinician DISAGREES. Starting revision...")
        new_concl = input("    What is the CORRECT conclusion? > ")
        
        # Get reference summary from the last true node
        reference_summary = ""
        if n2:
            reference_summary = n2.vertex.summary
            logging.info("Comparing against existing group profile.")
        else:
            logging.info("No reference group (New Root).")

        # Call LLM to find differences between Summaries [cite: 34-41]
        print("Identifying clinical differences...")
        conditions_list = llm_get_differentiating_conditions(new_patient_summary, reference_summary)
        
        # Select conditions (Logic remains similar to your request)
        selected_conditions = []
        
        if not conditions_list:
            logging.warning("No differences found automatically. Please enter manually.")
            while True:
                manual = input("    Enter condition (or Enter to finish): ").strip()
                if not manual: break
                selected_conditions.append(manual)
        else:
            print("\n    Differences found (Candidates for new rule):")
            for i, cond in enumerate(conditions_list):
                print(f"      {i+1}. {cond}")
            
            while True:
                print(f"\n    Selected: {json.dumps(selected_conditions)}")
                choice = input("    Select numbers (e.g. '1,3'), 'm' for manual, 'd' for done: ").strip().lower()
                
                if choice == 'd': 
                    if selected_conditions: break
                    logging.warning("Select at least one.")
                elif choice == 'm':
                    m = input("      Manual condition: ").strip()
                    if m: selected_conditions.append(m)
                else:
                    try:
                        indices = [int(x)-1 for x in choice.split(',')]
                        for idx in indices:
                            if 0 <= idx < len(conditions_list):
                                val = conditions_list[idx]
                                if val not in selected_conditions:
                                    selected_conditions.append(val)
                    except ValueError:
                        logging.warning("Invalid input.")

        # 4. Create New Node with Summary
        new_cond_string = json.dumps(selected_conditions)
        new_rule = Rule(new_cond_string, new_concl)
        
        # The new node starts with the current patient's summary as its "Group Profile"
        new_vertex = Vertex(new_rule, new_patient_summary)
        new_node = Node(new_vertex)

        # 5. Attach to Tree
        if self.root is None:
            self.root = new_node
        elif n1 == n2:
            n1.right = new_node # Exception
        else:
            n1.left = new_node  # Alternative

        logging.info(f"Rule created: If {new_cond_string} Then {new_concl}")

# --- Persistence and Main Loop ---

def load_tree() -> RDREngine:
    if os.path.exists(TREE_STORAGE_FILE):
        try:
            with open(TREE_STORAGE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return RDREngine()

def save_tree(engine):
    with open(TREE_STORAGE_FILE, "wb") as f:
        pickle.dump(engine, f)

def main():
    engine = load_tree()
    while True:
        try:
            fpath = input("\nEnter transcript JSON path (or 'q'): ").strip()
            if fpath.lower() == 'q': break
            if os.path.exists(fpath):
                engine.revise(fpath)
                save_tree(engine)
            else:
                print("File not found.")
        except KeyboardInterrupt:
            break
    save_tree(engine)

if __name__ == "__main__":
    main()