import streamlit as st
import json
import pandas as pd
from proposal_tools import store_proposal_section

def callback_function(output):
    """Callback to store the proposal section, show logs, and trigger next phase."""
    data = []  
    data.append({"Task": "Agent", "Value": output.agent})
    data.append({"Task": "Task Description", "Value": output.description})
    data.append({"Task": "Task Summary", "Value": output.summary})
    data.append({"Task": "Expected Output", "Value": output.expected_output})
    data.append({"Task": "Output", "Value": output.raw})
    
    store_proposal_section(
        st.session_state["proposal_id"],
        st.session_state["processing_phase"],
        str(output.raw),
        output.agent,
        output.summary,
        output.description,
    )
        
    df = pd.DataFrame(data)  
    if data:
        st.data_editor(df, column_config={ 
                        "Task": st.column_config.Column(width="medium"),  
                        "Value": st.column_config.Column(width="large")  
                    },hide_index=True, use_container_width=True)


