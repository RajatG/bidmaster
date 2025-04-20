import streamlit as st


def show_execution_modal(analysis="Pending",solution="Pending",planning="Pending"):
    # ✅ Create an empty container for the execution logs modal
    modal_placeholder = st.empty()
    
    """Displays Crew Execution Logs in a modal."""
    with modal_placeholder.container():
        with st.expander("📜 Crew Execution Log", expanded=True):
            st.text_area("Analysis Output", analysis, height=200)
            st.text_area("Solution Output", solution, height=200)
            st.text_area("Planning Output", planning, height=200)
            if st.button("Close Log"):
                modal_placeholder.empty()
