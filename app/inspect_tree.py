import sys
import pickle
import json
import os
import textwrap  # <-- ADDED for multi-line wrapping

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from rdr_engine import RDREngine, Node, Rule, Vertex
except ImportError:
    from app.rdr_engine import RDREngine, Node, Rule, Vertex

    
# --- PATH CONFIGURATION ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(CURRENT_DIR, '..', 'storage')
OUTPUT_DIR = os.path.join(CURRENT_DIR, '..','storage')

TREE_STORAGE_FILE = os.path.join(STORAGE_DIR, "rdr_tree_summary.pkl")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Interpretable_tree.txt")

# Colors for branches in terminal output (text file will not include colors)
RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"


def load_tree():
    try:
        with open(TREE_STORAGE_FILE, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print("[ERROR] Could not load tree:", e)
        exit()


def build_levels(root):
    """Return list of tree levels (BFS)."""
    if root is None:
        return []

    levels = []
    current = [root]

    # Stop when the entire level is 'None'
    while any(current):
        levels.append(current)
        next_level = []

        for node in current:
            if node:
                next_level.append(node.left)
                next_level.append(node.right)
            else:
                next_level.extend([None, None])

        current = next_level

    return levels


def get_node_text_blocks(node, spacing):
    """
    MODIFIED function.
    Returns two lists of strings: one for IF lines, one for THEN lines,
    all wrapped to the 'spacing' width.
    """
    if not node:
        return [], []

    # --- PARSE CONDITIONS (same as before) ---
    try:
        conditions_list = json.loads(node.vertex.rule.conditions)
        if isinstance(conditions_list, list):
            cond_text = " AND ".join(conditions_list)
        else:
            cond_text = str(conditions_list)
    except Exception:
        cond_text = node.vertex.rule.conditions

    if_text = f"IF: {cond_text}"
    then_text = f"THEN: {node.vertex.rule.conclusions}"

    # --- NEW MULTI-LINE LOGIC ---
    # Wrap the text to the width of the node's allocated space
    # (spacing - 2 for a little padding)
    wrapper = textwrap.TextWrapper(width=max(10, spacing - 2))
    
    if_lines = wrapper.wrap(if_text)
    then_lines = wrapper.wrap(then_text)

    # Center each line within the spacing
    centered_if_lines = [line.center(spacing) for line in if_lines]
    centered_then_lines = [line.center(spacing) for line in then_lines]

    return centered_if_lines, centered_then_lines


def format_tree_as_string(root):
    """Generate the full formatted tree string (no terminal color)."""
    levels = build_levels(root)
    if not levels:
        return "Tree is empty.\n"

    max_width = 180
    output_lines = []

    for i, level in enumerate(levels):
        spacing = max_width // max(1, len(level))

        # --- MODIFIED: Multi-line layout ---
        
        # Get wrapped text blocks for all nodes in this level
        level_blocks = [get_node_text_blocks(n, spacing) for n in level]
        
        # Find max height for IF and THEN blocks
        max_if_height = 0
        max_then_height = 0
        for if_block, then_block in level_blocks:
            max_if_height = max(max_if_height, len(if_block))
            max_then_height = max(max_then_height, len(then_block))

        # Print all IF lines
        for line_idx in range(max_if_height):
            line_str = ""
            for if_block, _ in level_blocks:
                if line_idx < len(if_block):
                    line_str += if_block[line_idx]
                else:
                    line_str += " ".center(spacing)  # Fill empty space
            output_lines.append(line_str)
        
        output_lines.append("") # Spacer

        # Print all THEN lines
        for line_idx in range(max_then_height):
            line_str = ""
            for _, then_block in level_blocks:
                if line_idx < len(then_block):
                    line_str += then_block[line_idx]
                else:
                    line_str += " ".center(spacing) # Fill empty space
            output_lines.append(line_str)
        
        output_lines.append("") # Spacer
        # --- END MODIFIED ---

        # Branches (no color in text file)
        if i < len(levels) - 1:
            branch_line = ""
            for node in level:
                half_spacing = spacing // 2
                if node:
                    left_branch = ("/" if node.left else " ").rjust(half_spacing)
                    right_branch = ("\\" if node.right else " ").ljust(half_spacing)
                    branch_line += left_branch + right_branch
                else:
                    branch_line += " ".center(spacing)
            output_lines.append(branch_line)

        output_lines.append("")
        output_lines.append("")

    return "\n".join(output_lines)


def print_tree_with_color_to_terminal(root):
    """Pretty print to terminal with colors for clarity."""
    levels = build_levels(root)
    if not levels:
        print("Tree is empty.\n")
        return

    max_width = 180

    for i, level in enumerate(levels):
        spacing = max_width // max(1, len(level))

        # --- MODIFIED: Multi-line layout ---
        level_blocks = [get_node_text_blocks(n, spacing) for n in level]
        max_if_height = max(len(b[0]) for b in level_blocks) if level_blocks else 0
        max_then_height = max(len(b[1]) for b in level_blocks) if level_blocks else 0

        # Print all IF lines
        for line_idx in range(max_if_height):
            line_str = "".join(
                b[0][line_idx] if line_idx < len(b[0]) else " ".center(spacing)
                for b in level_blocks
            )
            print(line_str)
        
        print("") # Spacer

        # Print all THEN lines
        for line_idx in range(max_then_height):
            line_str = "".join(
                b[1][line_idx] if line_idx < len(b[1]) else " ".center(spacing)
                for b in level_blocks
            )
            print(line_str)
        
        print("") # Spacer
        # --- END MODIFIED ---

        if i < len(levels) - 1:
            branch_line = ""
            for node in level:
                half_spacing = spacing // 2
                if node:
                    # Left branch (FALSE)
                    if node.left:
                        branch_line += " ".rjust(half_spacing - 1) + RED + "/" + RESET
                    else:
                        branch_line += " ".ljust(half_spacing)
                    
                    # Right branch (TRUE)
                    if node.right:
                        branch_line += GREEN + "\\" + RESET + " ".ljust(half_spacing - 1)
                    else:
                        branch_line += " ".ljust(half_spacing)
                else:
                    branch_line += " ".center(spacing)
            print(branch_line, "\n")


def main():
    engine = load_tree()
    max_width = 180

    print("\n✅ Generating visual RDR tree representation...\n")

    # --- COMMENTED OUT as requested ---
    # print(f"RDR Tree (in {TREE_STORAGE_FILE}):")
    # print(f"({RED}False = Left{RESET}, {GREEN}True = Right{RESET})")
    # print("-" * max_width)
    # print_tree_with_color_to_terminal(engine.root)
    # print("-" * max_width)

    # Save clean text tree to file
    tree_text = format_tree_as_string(engine.root)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"RDR Tree (from {TREE_STORAGE_FILE})\n")
        f.write("(False = Left, True = Right)\n")
        f.write("-" * max_width + "\n")
        f.write(tree_text)

    print(f"\n📄 Output saved to: {OUTPUT_FILE}")
    print("This file should now be readable with multi-line nodes.")
    print("Done.\n")


if __name__ == "__main__":
    main()