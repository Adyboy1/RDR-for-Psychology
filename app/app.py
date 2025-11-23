import streamlit as st
import os
import json
import sys
import pickle
import graphviz
import textwrap

# --- PATH CONFIGURATION ---
# Ensures we can import modules from the current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from rdr_engine import RDREngine, Node, Rule, Vertex, TREE_STORAGE_FILE
    from llm_api import (
        llm_check_condition, 
        llm_get_differentiating_conditions, 
        llm_generate_summary, 
        llm_merge_summaries
    )
except ImportError:
    from app.rdr_engine import RDREngine, Node, Rule, Vertex, TREE_STORAGE_FILE
    from app.llm_api import (
        llm_check_condition, 
        llm_get_differentiating_conditions, 
        llm_generate_summary, 
        llm_merge_summaries
    )

# --- PAGE SETUP ---
st.set_page_config(page_title="RDR Clinical Engine", layout="wide")
st.title("🧠 Clinical RDR Knowledge Base")

# --- SESSION STATE INITIALIZATION ---
if 'engine' not in st.session_state:
    if os.path.exists(TREE_STORAGE_FILE):
        try:
            with open(TREE_STORAGE_FILE, "rb") as f:
                st.session_state.engine = pickle.load(f)
        except:
            st.session_state.engine = RDREngine()
    else:
        st.session_state.engine = RDREngine()

if 'current_summary' not in st.session_state:
    st.session_state.current_summary = None
if 'interpretation_result' not in st.session_state:
    st.session_state.interpretation_result = None
if 'diff_conditions' not in st.session_state:
    st.session_state.diff_conditions = []

# --- VISUALIZATION LOGIC ---
def build_graph(root):
    """
    Constructs a Graphviz object for the decision tree.
    Uses aggressive wrapping and standard splines for a more compact tree.
    """
    dot = graphviz.Digraph()
    
    # LAYOUT SETTINGS
    # Removing 'ortho' splines to allow tighter packing
    dot.attr(rankdir='TB')        
    dot.attr(nodesep='0.5')       
    dot.attr(ranksep='1.0')       
    
    # NODE STYLE
    # Using 'Mrecord' gives rounded corners and nice internal spacing
    dot.attr('node', shape='Mrecord', style='filled', fillcolor='#F0F2F6', 
             fontname='Arial', fontsize='10', margin='0.1')
    
    if not root:
        dot.node("empty", "Empty Tree", style='dashed')
        return dot

    def format_label(node):
        """Formats the node text with aggressive wrapping."""
        # 1. Get Condition Text
        try:
            conds = json.loads(node.vertex.rule.conditions)
            if isinstance(conds, list):
                # Simple bullets
                cond_list = [f"• {c}" for c in conds]
                cond_text = "\n".join(cond_list)
            else:
                cond_text = str(conds)
        except:
            cond_text = node.vertex.rule.conditions
            
        # 2. Get Conclusion Text
        concl_text = node.vertex.rule.conclusions
        
        # 3. Wrap Text (Target 25 chars for very vertical boxes)
        wrapper = textwrap.TextWrapper(width=25, break_long_words=False, replace_whitespace=False)
        
        wrapped_cond_lines = wrapper.wrap(cond_text)
        final_cond = "\\n".join(wrapped_cond_lines)
        
        wrapped_concl_lines = wrapper.wrap(concl_text)
        final_concl = "\\n".join(wrapped_concl_lines)
        
        # 4. Assemble Label
        # Mrecord allows formatting with { | } to split boxes
        # This creates a divider line between IF and THEN
        return f"{{ IF:\\n{final_cond} | THEN:\\n{final_concl} }}"

    def add_nodes_recursive(node, node_id):
        # Add Node
        label = format_label(node)
        dot.node(node_id, label)
        
        # Add Edges and Children
        if node.left:
            left_id = f"{node_id}L"
            add_nodes_recursive(node.left, left_id)
            # Label the edge near the tail
            dot.edge(node_id, left_id, label=" False", color="#D32F2F", fontcolor="#D32F2F")
            
        if node.right:
            right_id = f"{node_id}R"
            add_nodes_recursive(node.right, right_id)
            # Label the edge near the tail
            dot.edge(node_id, right_id, label=" True", color="#388E3C", fontcolor="#388E3C")

    # Start recursion
    add_nodes_recursive(root, "root")
    return dot

# --- SIDEBAR ---
with st.sidebar:
    st.header("Knowledge Tree")
    if st.button("Refresh Tree"):
        pass 
    
    if st.session_state.engine.root:
        graph = build_graph(st.session_state.engine.root)
        st.graphviz_chart(graph, use_container_width=True)
    else:
        st.info("Tree is empty. Process a case to start.")

# --- MAIN CONTENT ---

tab1, tab2 = st.tabs(["Case Processing", "Debug / Manual Input"])

with tab1:
    st.subheader("1. Input Transcript")
    
    uploaded_file = st.file_uploader("Upload Patient Transcript (JSON)", type="json")
    manual_path = st.text_input("Or enter file path (e.g., patient_A.json):")
    
    transcript_path = None
    if uploaded_file:
        with open("temp_transcript.json", "wb") as f:
            f.write(uploaded_file.getbuffer())
        transcript_path = "temp_transcript.json"
    elif manual_path:
        if os.path.exists(manual_path):
            transcript_path = manual_path
        else:
            t_path = os.path.join(CURRENT_DIR, '..', 'transcripts', manual_path)
            if os.path.exists(t_path):
                transcript_path = t_path

    if st.button("Analyze Case") and transcript_path:
        with st.spinner("Generating Clinical Summary..."):
            summary = llm_generate_summary(transcript_path)
            st.session_state.current_summary = summary
            
        with st.spinner("Interpreting Rules..."):
            n1, n2 = st.session_state.engine.interpret(summary)
            st.session_state.interpretation_result = (n1, n2)
            st.session_state.diff_conditions = [] 

    # --- RESULTS AREA ---
    if st.session_state.current_summary:
        st.divider()
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("### 📄 Clinical Summary")
            st.info(st.session_state.current_summary)
            
        with col_b:
            st.markdown("### 🤖 System Conclusion")
            n1, n2 = st.session_state.interpretation_result
            
            if n2:
                st.success(f"**{n2.vertex.rule.conclusions}**")
                st.caption("Based on matching rule in the tree.")
            else:
                st.warning("**No Conclusion (Empty Tree or Fallback)**")
            
            st.markdown("#### Clinician Review")
            
            if st.button("✅ Agree (Correct)"):
                if n2:
                    with st.spinner("Merging profile..."):
                        updated = llm_merge_summaries(n2.vertex.summary, st.session_state.current_summary)
                        n2.vertex.summary = updated
                        with open(TREE_STORAGE_FILE, "wb") as f:
                            pickle.dump(st.session_state.engine, f)
                        st.success("Knowledge base updated (Profile Merged)!")
                        st.rerun()

            if st.button("❌ Disagree (Revise)"):
                st.session_state.show_revision_form = True

        # --- REVISION FORM ---
        if st.session_state.get("show_revision_form"):
            st.divider()
            st.subheader("🔧 Knowledge Acquisition (Revise)")
            
            new_conclusion = st.text_input("What is the CORRECT conclusion?")
            
            if st.button("🔍 Find Differences (Ask AI)"):
                n1, n2 = st.session_state.interpretation_result
                ref_sum = n2.vertex.summary if n2 else ""
                with st.spinner("Comparing cases..."):
                    conds = llm_get_differentiating_conditions(st.session_state.current_summary, ref_sum)
                    st.session_state.diff_conditions = conds
            
            final_conditions = []
            if st.session_state.diff_conditions:
                st.write("Select distinguishing conditions:")
                for cond in st.session_state.diff_conditions:
                    if st.checkbox(cond, key=cond):
                        final_conditions.append(cond)
            
            manual_cond = st.text_input("Or enter manual condition:")
            if manual_cond:
                final_conditions.append(manual_cond)
                
            if st.button("💾 Save New Rule"):
                if not new_conclusion or not final_conditions:
                    st.error("Please provide a conclusion and at least one condition.")
                else:
                    import json
                    cond_json = json.dumps(final_conditions)
                    new_rule = Rule(cond_json, new_conclusion)
                    new_vertex = Vertex(new_rule, st.session_state.current_summary)
                    new_node = Node(new_vertex)
                    
                    n1, n2 = st.session_state.interpretation_result
                    
                    if st.session_state.engine.root is None:
                        st.session_state.engine.root = new_node
                    elif n1 == n2:
                        n1.right = new_node
                    else:
                        n1.left = new_node
                        
                    with open(TREE_STORAGE_FILE, "wb") as f:
                        pickle.dump(st.session_state.engine, f)
                    
                    st.success("New rule added successfully!")
                    st.session_state.show_revision_form = False
                    st.rerun()