import os, time, sqlite3, uuid
import streamlit as st
import yaml
import pandas as pd
from crewai_tools import ScrapeWebsiteTool
from typing import Dict, Any, Optional


# Initialize session state for page navigation
if "current_page" not in st.session_state:
    st.session_state.current_page = "main"

if st.session_state.current_page == "main":
    st.set_page_config(page_title="🎯 BidMaster", layout="wide")


import proposal_team
from proposal_tools import parse_store_input_docs, store_proposal_section, get_proposal_sections


def load_yaml_config(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

def save_yaml_config(file_path, data):
    with open(file_path, "w") as file:
        yaml.dump(data, file, default_flow_style=False)

# ✅ Function to Display Sections in a Modal
def show_section_modal(section_head, content):
    """Displays the proposal section in a modal."""
    section_placeholder = st.empty()
    with section_placeholder.container():
        with st.expander(f"📄 {section_head}", expanded=False):
            st.markdown(content, unsafe_allow_html=True) 

                

# ✅ Function to Display the Final Proposal as a PDF in a Modal
def show_pdf_modal(pdf_path):
    """Displays the final proposal PDF inside a modal."""
    with modal_placeholder.container():
        with st.expander("📄 Final Proposal", expanded=False):
            st.markdown(f'<iframe src="{pdf_path}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)

# ✅ Function to Display Sections (Clickable for Modal View)
CORPORATE_HEADER = "Acme Corp Proposal"  # Replace with your actual header
CORPORATE_FOOTER = "Confidential"  # Replace with your actual footer
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

def format_and_download_section_docx(section_name, content, proposal_id, logo_path=None):
    """Formats the section output into a DOCX file and provides a download."""

    document = Document()

    # Header
    header = document.sections[0].header
    header_paragraph = header.paragraphs[0]
    header_paragraph.text = CORPORATE_HEADER
    header_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Logo (Optional)
    if logo_path:
        try:
            header.shapes.add_picture(logo_path, Inches(1))  # Adjust size as needed
        except FileNotFoundError:
            st.warning(f"Logo file not found at {logo_path}")

    # Section Name
    section_paragraph = document.add_paragraph()
    section_paragraph.text = f"Section: {section_name.capitalize()}"
    section_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    section_paragraph.style.font.size = Pt(14)

    # Content (Render Markdown)
    # Note:  docx doesn't fully support markdown.  For robust conversion, consider a library like 'md2docx'
    document.add_paragraph(content)  # Simple text for now

    # Footer
    footer = document.sections[0].footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.text = CORPORATE_FOOTER
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    filename = f"{proposal_id}_{section_name}.docx"
    # Save the DOCX file to a BytesIO object
    from io import BytesIO
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    st.download_button(
        label=f"⬇️ Download {section_name.capitalize()} (DOCX)",
        data=buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

def format_and_download_section(section_name, content, proposal_id):
    """Formats the section output and provides a download."""

    formatted_content = f"{CORPORATE_HEADER}\n\n"
    formatted_content += f"Section: {section_name.capitalize()}\n\n"
    formatted_content += content
    formatted_content += f"\n\n{CORPORATE_FOOTER}"

    filename = f"{proposal_id}_{section_name}.txt"  # Simple text download
    st.download_button(
        label=f"⬇️ Download {section_name.capitalize()}",
        data=formatted_content.encode(),
        file_name=filename,
        mime="text/plain"
    )

def display_sections():
    sections = get_proposal_sections(st.session_state["proposal_id"])

    if not sections:
        st.info("Crew generated proposal outputs will appear here...")
    else:
        for phase_name, phase_data in sections.items():
            phase_output = phase_data.get("phase_output", "No output available.")
            show_section_modal(phase_name.capitalize() + " Output", phase_output)
            format_and_download_section_docx(phase_name, phase_output, st.session_state["proposal_id"])

            if phase_data.get("tasks"):
                with st.expander(f"Detailed Tasks for {phase_name.capitalize()}", expanded=False):
                    for task in phase_data["tasks"]:
                        st.markdown(f"**Task:** {task['task_name'].capitalize()}")
                        st.markdown(f"**Output:** {task['output']}", unsafe_allow_html=True) # Changed to st.markdown()
                        st.caption(f"Created at: {task['created_at']}")
                        st.divider()

    # ✅ Show Final Proposal as PDF Link
    final_pdf_path = f"uploads/{st.session_state['proposal_id']}/Final_Proposal.pdf"
    if os.path.exists(final_pdf_path):
        if st.button("📄 View Final Proposal", key="final_proposal"):
            show_pdf_modal(final_pdf_path)
    
# Function to retrieve chat history
def get_chat_history(proposal_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, message FROM proposal_chat WHERE proposal_id = ? ORDER BY timestamp ASC", (proposal_id,))
    chat_history = cursor.fetchall()
    conn.close()
    return [{"role": msg[0], "content": msg[1]} for msg in chat_history]

# Function to store chat messages
def store_chat_message(proposal_id, role, message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO proposal_chat (proposal_id, role, message, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (proposal_id, role, message))
    conn.commit()
    conn.close()

# Function to create a new proposal record
def create_proposal_master(proposal_name):
    proposal_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO proposal_master (proposal_id, proposal_name) VALUES (?, ?)", (proposal_id, proposal_name))
    conn.commit()
    conn.close()
    return proposal_id    



def execute_task_with_chat_input(task, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Executes a task, handling chat inputs if required.
    """
    # Check if task needs input fields
    input_fields = getattr(task, "input_fields", None)
    print(f"--- execute_task_with_chat_input: Task: {task.name}, Input Fields: {input_fields} ---")  # Debugging
    if st.session_state.waiting_for_input:
        print(f"--- execute_task_with_chat_input: Waiting for input: {st.session_state.input_task.name}, Current Task: {task.name} ---") # Debugging
    if st.session_state.input_task == task:
        print(f"--- execute_task_with_chat_input: Input task matches ---") # Debugging

    # If waiting for user input (set in a previous cycle)
    if st.session_state.waiting_for_input and st.session_state.input_task == task:
        user_inputs = st.session_state.user_task_inputs
        inputs.update(user_inputs)
        st.session_state.waiting_for_input = False  # Reset for next task
        st.session_state.user_task_inputs = {}
        st.session_state.input_task = None
        try:
            task.execute(inputs=inputs)
            return {}  # Indicate successful execution
        except Exception as e:
            st.error(f"❌ Error executing task {task.name} with chat inputs: {e}")
            return {}
    elif input_fields:
        # We need to pause and collect inputs
        st.session_state.waiting_for_input = True
        st.session_state.input_task = task
        st.session_state.input_fields = input_fields
        st.rerun()
        return None
    else:
        try:
            task_result = task.execute(inputs=inputs)
            print(f"--- execute_task_with_chat_input: Task executed without input ---")  # Debugging
            return {"output": task_result}  # Return the output
        except Exception as e:
            st.error(f"❌ Error executing task {task.name}: {e}")
            return {"error": str(e)}
    
if "waiting_for_input" not in st.session_state:
    st.session_state.waiting_for_input = False
    st.session_state.input_task = None
    st.session_state.input_fields = {}
    st.session_state.user_task_inputs = {}
        
# --- Configuration Management ---
CONFIG_DIR = "config"

config_files = {
    "Agents": os.path.join(CONFIG_DIR, "agents.yaml"),
    "Tasks": os.path.join(CONFIG_DIR, "tasks.yaml"),
    "LLM": os.path.join(CONFIG_DIR, "llm.yaml"),
    "External Tools": os.path.join(CONFIG_DIR, "tools.yaml"),
}

configs = {name: load_yaml_config(path) for name, path in config_files.items()}


DB_PATH = "proposals.db"
saved_paths = []
if "proposal_id" not in st.session_state:
    st.session_state["proposal_id"] = None
    
if st.session_state.current_page == "main":

    st.markdown("<h1 style='text-align: center;'>🎯 BidMaster</h1>", unsafe_allow_html=True)

    modal_placeholder = st.empty()
    # ✅ Sidebar - Proposal Selection
    st.sidebar.header("Proposal Management")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT proposal_id, proposal_name FROM proposal_master ORDER BY created_at DESC")
    proposals = cursor.fetchall()
    conn.close()

    existing_proposal = st.sidebar.radio("Choose an option:", ["🆕 Start New Proposal", "📂 Continue Existing Proposal"], index=0)

    if existing_proposal == "📂 Continue Existing Proposal":
        if proposals:
            selected_proposal = st.sidebar.selectbox("Choose a Proposal:", proposals, format_func=lambda x: x[1])
            st.session_state["proposal_id"] = selected_proposal[0]
        else:
            st.sidebar.warning("No existing proposals found.")
            st.stop()
    else:
        st.session_state["proposal_id"] = None
        proposal_name = st.sidebar.text_input("Enter Proposal Name:")


    # ✅ File Upload Section
    st.sidebar.subheader("📂 Upload Documents")
    uploaded_files = st.sidebar.file_uploader("Upload all proposal documents (PDF/DOCX)", 
                                            type=["pdf", "docx"], accept_multiple_files=True)

    # ✅ Store Uploaded Files
    if uploaded_files:
        if existing_proposal == "🆕 Start New Proposal" and proposal_name.strip() and st.session_state["proposal_id"] == None:
            st.session_state["proposal_id"] = create_proposal_master(proposal_name)
        elif not st.session_state["proposal_id"]:
            st.sidebar.error("⚠️ Please enter a proposal name before uploading files.")
            st.stop()

        upload_dir = f"uploads/{st.session_state['proposal_id']}/"
        
        os.makedirs(upload_dir, exist_ok=True)
    
        saved_paths = []
        for file in uploaded_files:
            file_path = os.path.join(upload_dir, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            saved_paths.append(file_path)
        st.sidebar.success("✅ All files uploaded successfully!")

    # ✅ Start Proposal Generation Button
    st.sidebar.subheader("🔄 Progress")
    
    if st.session_state["proposal_id"] and st.sidebar.button("🚀 Start Proposal Generation"):
        parse_store_input_docs(st.session_state["proposal_id"], saved_paths)
        inputs = {'proposal_id': st.session_state["proposal_id"], 'document_list': saved_paths}
        st.session_state.all_tasks_input = {} # Stores all task inputs

        # ✅ Create an empty container for the execution logs modal
        modal_placeholder = st.empty()

        with modal_placeholder.container():
            with st.expander("📜 Crew Execution Log", expanded=True):

                # ✅ Start Analysis Phase
                st.session_state["processing_phase"] = "analysis"
                pd.set_option("display.max_colwidth", None)

               # Collect all tasks for the current crew
                all_tasks = proposal_team.proposal_analysis_crew.tasks.copy() # important to copy
                all_tasks.extend(proposal_team.proposal_solution_crew.tasks.copy())
                all_tasks.extend(proposal_team.proposal_drafting_crew.tasks.copy())
                #print(f"All tasks: {all_tasks}") # Add this line

                current_task_index = 0
                while current_task_index < len(all_tasks):
                    task = all_tasks[current_task_index]
                    print(f"Inside loop - Current task index: {current_task_index}, Task: {task}, Type: {type(task)}")
                    task_inputs = st.session_state.all_tasks_input.get(task.name, {}) # Retrieve stored inputs

                    if not st.session_state.waiting_for_input:
                        with st.spinner(f"🔄 Processing Task: {task.name} in {st.session_state['processing_phase']}..."):
                            print(f"Before execute_task_with_chat_input - Task: {task}, Type: {type(task)}")
                            result = execute_task_with_chat_input(task, inputs.copy().update(task_inputs)) # Pass inputs to the task
                            print(f"After execute_task_with_chat_input - Result: {result}")

                            if result is None:
                                break  # Wait for user input
                            else:
                                current_task_index += 1 # Move to the next task

                    else:
                        break # Wait for input
                    
                # Input Handling in Chat
                if st.session_state.waiting_for_input:
                    st.subheader(f"📝 Provide inputs for task: {st.session_state.input_task.name}")
                    user_inputs = {}
                    for key, field in st.session_state.input_fields.items():
                        prompt = field.get("prompt", f"Enter value for {key}")
                        user_inputs[key] = st.text_input(prompt, key=key)

                    if st.button("Submit Inputs"):
                        st.session_state.user_task_inputs = user_inputs
                        st.rerun()
                                                       
                with st.spinner("🔄 Processing Analysis Phase..."):
                    st.session_state.analysis_output = proposal_team.proposal_analysis_crew.kickoff(inputs=inputs)
                    store_proposal_section(st.session_state["proposal_id"], st.session_state["processing_phase"], str(st.session_state.analysis_output))
                    st.session_state.chat_messages.append({"role": "analyst", "content": "🔄 Requirement Analysis Complete..."})
                    data = []   
                    data.append({"Task": "Output", "Value": st.session_state.analysis_output.raw})
                    data.append({"Task": "Token Usage", "Value": st.session_state.analysis_output.token_usage})
                    df = pd.DataFrame(data)  # 
                    st.data_editor(df,  
                                column_config={ 
                                    "Task": st.column_config.Column(width="medium"),  
                                    "Value": st.column_config.Column(width="large")  
                                }, hide_index=True, use_container_width=True)
                    os.rename("./logs/analysis.txt",f"./logs/{st.session_state['proposal_id']}_analysis.log")
                st.session_state["processing_phase"] = "approach"
                with st.spinner("🔄 Processing Solutioning Phase..."):
                    st.session_state.solution_output  = proposal_team.proposal_solution_crew.kickoff(inputs=inputs)
                    store_proposal_section(st.session_state["proposal_id"], st.session_state["processing_phase"], str(st.session_state.solution_output ))
                    st.session_state.chat_messages.append({"role": "solution", "content": "🔄 Proposed Solution completion..."})
                    data = []  
                    data.append({"Task": "Output", "Value": st.session_state.solution_output.raw})
                    data.append({"Task": "Token Usage", "Value": st.session_state.solution_output.token_usage})
                    df = pd.DataFrame(data)  # 
                    st.data_editor(df,  
                                column_config={ 
                                    "Task": st.column_config.Column(width="medium"),  
                                    "Value": st.column_config.Column(width="large")  
                                }, hide_index=True, use_container_width=True)
                    os.rename("./logs/approach.txt",f"./logs/{st.session_state['proposal_id']}_approach.log")
                                
                st.session_state["processing_phase"] = "draft"
                with st.spinner("🔄 Processing Final Draft Phase..."):
                    st.session_state.planning_output  = proposal_team.proposal_drafting_crew.kickoff(inputs=inputs)
                    store_proposal_section(st.session_state["proposal_id"], st.session_state["processing_phase"],str(st.session_state.planning_output))
                    st.session_state.chat_messages.append({"role": "writer", "content": "🔄 Proposal Final Draft completed..."})
                    data = []  
                    data.append({"Task": "Output", "Value": st.session_state.planning_output.raw})
                    data.append({"Task": "Token Usage", "Value": st.session_state.planning_output.token_usage})
                    df = pd.DataFrame(data)  # 
                    st.data_editor(df,  
                                column_config={ 
                                    "Task": st.column_config.Column(width="medium"),  
                                    "Value": st.column_config.Column(width="large")  
                                }, hide_index=True, use_container_width=True)
                    os.rename("./logs/draft.txt",f"./logs/{st.session_state['proposal_id']}_draft.log")
                        
                st.session_state["processing_phase"] = None  
                if st.button("Close Log"):
                    modal_placeholder.empty()
                    
    elif st.session_state["proposal_id"]:
   
        # ✅ Create an empty container for the execution logs modal
        modal_placeholder = st.empty()
        
        with modal_placeholder.container():
            with st.expander("📜 Crew Execution Log", expanded=False):
                log_files = [f"./logs/{st.session_state['proposal_id']}_analysis.log", f"./logs/{st.session_state['proposal_id']}_approach.log", f"./logs/{st.session_state['proposal_id']}_draft.log"]
                log_contents = {}

                for log_file in log_files:
                    if os.path.exists(log_file):
                        with open(log_file, "r") as file:
                            log_contents[log_file] = file.read()
                    else:
                        log_contents[log_file] = "No previous Log file found."

                for log_file, content in log_contents.items():
                    st.text(content)
                        
    if st.button("⚙️ Open Configuration"):
        st.session_state.current_page = "config"
        st.rerun()  # Trigger page switch
        
    # ✅ Main Page UI
    st.subheader("Proposal Hub", divider=True)

    # ✅ Display AI-Generated Proposal Sections
    st.subheader("📄 Generated outputs")
    display_sections()

    # ✅ Chat UI
    st.subheader("💬 Message Board")
    chat_history = get_chat_history(st.session_state["proposal_id"])
    if not chat_history:
        st.info("Proposal Chat history will appear here...")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = chat_history  

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ✅ Handle User Feedback
    user_input = st.chat_input("Send a message or feedback ...")
    if user_input:
        store_chat_message(st.session_state["proposal_id"], "user", user_input)
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        if "feedback" in user_input.lower():
            phase = st.session_state.get("processing_phase", "analysis")
            feedback_inputs = {'proposal_id': st.session_state["proposal_id"], 'user_feedback': user_input}

            if phase == "analysis":
                proposal_team.proposal_analysis_crew.kickoff(feedback_inputs)
            elif phase == "approach":
                proposal_team.proposal_solution_crew.kickoff(feedback_inputs)
            elif phase == "draft":
                proposal_team.proposal_final_crew.kickoff(feedback_inputs)

            st.session_state.chat_messages.append({"role": "assistant", "content": "🔄 Updating proposal based on feedback..."})
            st.rerun()


elif st.session_state.current_page == "config":
    
    # --- Configuration Page ---
    st.set_page_config(page_title="⚙️ Configuration", layout="wide") # needed to avoid error when switching from main page
    

    # Close Configuration Button (go back to Master Page)
    if st.button("❌ Close Configuration"):
        st.session_state.current_page = "main"
        st.rerun()  # Trigger page switch

    st.title("⚙️ Configuration Panel")

    # Configuration Tabs
    tabs = st.tabs(list(config_files.keys()))

    for i, (name, path) in enumerate(config_files.items()):
        with tabs[i]:
            st.subheader(f"{name} Configuration")
            
            # Editable fields
            def edit_agent(agent, idx):
                st.subheader(f"Agent {idx + 1}: {agent['name']}")
                agent['name'] = st.text_input("Name", agent['name'], key=f"agent_name_{idx}")
                agent['role'] = st.text_input("Role", agent['role'], key=f"agent_role_{idx}")
                agent['backstory'] = st.text_area("Backstory", agent['backstory'], key=f"agent_backstory_{idx}")
                agent['goal'] = st.text_area("Goal", agent['goal'], key=f"agent_goal_{idx}")
                agent['tools'] = st.text_area("Tools (comma-separated)", ", ".join(agent['tools']), key=f"agent_tools_{idx}").split(', ')
                return agent

            # Editable fields
            def edit_task(task, idx):
                print(task)
                st.subheader(f"Task {idx + 1}: {task['name']}")
                task['name'] = st.text_input("Name", task['name'], key=f"task_name_{idx}")
                task['description'] = st.text_input("Description", task['description'], key=f"task_description_{idx}")
                task['expected_output'] = st.text_area("Expected Output", task['expected_output'], key=f"task_expected_output_{idx}")
                task['agent'] = st.text_area("Agent", task['agent'], key=f"task_agent_{idx}")
                if task.get("dependencies"):
                    task['dependencies'] = st.text_area("Dependencies", task['dependencies'], key=f"task_dependencies_{idx}")
                return task
            def edit_llm(llm, idx):
                st.subheader(f"LLM {idx + 1}: {llm['agent']}")
                llm['agent'] = st.text_area("Agent", llm['agent'], key=f"agent_{idx}")
                llm['name'] = st.text_input("Name", llm['name'], key=f"name_{idx}")
                llm['base_url'] = st.text_input("Base URL", llm['base_url'], key=f"base_url_{idx}")
                llm['api_key'] = st.text_area("API Key", llm['api_key'], key=f"api_key_{idx}")
                llm['temperature'] = st.text_area("temperature",  llm['temperature'], key=f"temperature_{idx}").split(', ')
                return llm
            
            def edit_tools(tools, idx):
                st.text("WIP")
             
            if name == "Agents":
                # Loop through agents
                for idx, agent in enumerate(configs["Agents"]["agents"] ):
                    configs['Agents'][idx] = edit_agent(agent, idx)
            elif name == "Tasks":                
                # Loop through agents
                for idx, task in enumerate(configs["Tasks"]["tasks"] ):
                    configs['Tasks'][idx] = edit_task(task, idx)
            elif name == "LLM":
                # Loop through llm
                for idx, llm in enumerate(configs['LLM']['llm']):
                    configs['LLM'][idx] = edit_llm(llm, idx)
            elif name == "External Tools":
                if configs.get('External Tools'):
                    for idx, tool in enumerate(configs['External Tools']):
                        configs['External Tools'][idx] = edit_tools(tool, idx)


            # Save Button
            if st.button(f"Save {name} Config", key=f"save_{name}"):
                try:
                    save_yaml_config(path, configs[name]) 
                    st.success(f"{name} configuration saved successfully!")
                except yaml.YAMLError as e:
                    st.error(f"Error saving {name} config: {e}")

            # Reload Button
            if st.button(f"Reload {name} Config", key=f"reload_{name}"):
                st.rerun()






        