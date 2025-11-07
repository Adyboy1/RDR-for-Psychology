# inspect_tree.py
import pickle
from rdr_engine import RDREngine, Node, Rule, Vertex

TREE_STORAGE_FILE = "rdr_tree.pkl"
OUTPUT_FILE = "Interpretable_tree.txt"

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


def node_label(node):
    """Return label lines: condition + conclusion."""
    if not node:
        return [" ", " "]

    return [
        f"IF: {node.vertex.rule.conditions}",
        f"THEN: {node.vertex.rule.conclusions}"
    ]


def format_tree_as_string(root):
    """Generate the full formatted tree string (no terminal color)."""
    levels = build_levels(root)
    if not levels:
        return "Tree is empty.\n"

    max_width = 180
    output_lines = []

    for i, level in enumerate(levels):
        spacing = max_width // (len(level) + 1)

        # Conditions
        cond_line = "".join(node_label(n)[0].center(spacing) for n in level)
        output_lines.append(cond_line)
        output_lines.append("")  # vertical spacing

        # Conclusions
        conc_line = "".join(node_label(n)[1].center(spacing) for n in level)
        output_lines.append(conc_line)
        output_lines.append("")

        # Branches (no color in text file)
        if i < len(levels) - 1:
            branch_line = ""
            for node in level:
                if node:
                    branch_line += "/".rjust(spacing//2) + "\\".ljust(spacing//2)
                else:
                    branch_line += " ".center(spacing)
            output_lines.append(branch_line)

        output_lines.append("")  # spacing between levels
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
        spacing = max_width // (len(level) + 1)

        cond_line = "".join(node_label(n)[0].center(spacing) for n in level)
        print(cond_line, "\n")

        conc_line = "".join(node_label(n)[1].center(spacing) for n in level)
        print(conc_line, "\n")

        if i < len(levels) - 1:
            branch_line = ""
            for node in level:
                if node:
                    branch_line += RED + "/" + RESET
                    branch_line += " " * (spacing - 2)
                    branch_line += GREEN + "\\" + RESET
                else:
                    branch_line += " ".center(spacing)
            print(branch_line, "\n")


def main():
    engine = load_tree()

    print("\n✅ Generating visual RDR tree representation...\n")

    # Print colored tree to terminal
    print_tree_with_color_to_terminal(engine.root)

    # Save clean text tree to file
    tree_text = format_tree_as_string(engine.root)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(tree_text)

    print(f"\n📄 Output saved to: {OUTPUT_FILE}")
    print("Done.\n")


if __name__ == "__main__":
    main()
