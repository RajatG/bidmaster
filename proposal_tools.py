from langchain.tools import Tool
import sqlite3
import PyPDF2
import os
from docx import Document
import pickle  # For loading the trained model
from crewai_tools import ScrapeWebsiteTool

MODEL_PATH = "effort_model.pkl"

# Database setup
DB_PATH = "proposals.db"

def init_db():
    
    """Initialize the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
        
    # Proposal master table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proposal_master (
            proposal_id TEXT PRIMARY KEY,
            proposal_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Proposal inputs storage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proposal_inputs (
            proposal_id TEXT,
            section_name TEXT,
            content TEXT,
            reviewed INTEGER,
            PRIMARY KEY (proposal_id, section_name),
            FOREIGN KEY (proposal_id) REFERENCES proposal_master(proposal_id)
        )
    """)
    
    # Master table for processing phases
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proposal_processing_phase (
            proposal_id TEXT,
            phase_name TEXT,
            content TEXT,
            reviewed INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (proposal_id, phase_name),
            FOREIGN KEY (proposal_id) REFERENCES proposal_master(proposal_id)
        )
    """)
    
        # Detail table for individual task outputs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proposal_task_output (
            output_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT,
            phase_name TEXT,
            task_name TEXT,
            agent_name TEXT,
            task_description TEXT,
            output TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proposal_id) REFERENCES proposal_master(proposal_id),
            FOREIGN KEY (phase_name) REFERENCES proposal_processing_phase(phase_name)
        )
    """)
    

    # Pricing data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_pricing (
            role TEXT PRIMARY KEY,
            rate INTEGER
        )
    """)

    # Resource Pyramid structure
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_pyramid (
            project_type TEXT,
            category TEXT,
            manager_percentage REAL,
            developer_percentage REAL,
            qa_percentage REAL,
            PRIMARY KEY (project_type, category)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---- Parsing and Storing Proposals ----
def parse_store_input_docs(proposal_id: str, document_list: list):
    """Extracts text from uploaded documents and stores it in the DB"""
    
    for file_path in document_list:
        
        file_ext = os.path.splitext(file_path)[-1].lower()
        
        combined_text = ""
        documents_list = ", ".join(document_list)

        if file_ext == ".pdf":
            with open(file_path, "rb") as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif file_ext in [".doc", ".docx"]:
            doc = Document(file_path)
            extracted_text = "\n".join([para.text for para in doc.paragraphs])
        
        combined_text = "\n\n".join(extracted_text[:100] + ("..." if len(extracted_text) > 100 else ""))
        # Store extracted text
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO proposal_inputs (proposal_id, section_name, content, reviewed) VALUES (?, ?, ?, ?)",
                    (proposal_id, os.path.basename(file_path), extracted_text, 0 ))
        conn.commit()
        conn.close()

    return {
        "proposal_id": proposal_id,
        "summary": combined_text,
        "documents": documents_list
    }

parse_store_input_docs_tool = Tool.from_function(
    func=parse_store_input_docs,
    name="parse_and_store_proposal",
    description="Extracts text from a proposal document and stores them in the database."
)

def read_proposal_inputs(proposal_id):
    """Reads the proposal inputs given a proposal_id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT section_name, content FROM proposal_inputs WHERE proposal_id = ?", (proposal_id,))
    inputs = cursor.fetchall()
    conn.close()
    print(inputs)
    return {input[0]: input[1] for input in inputs} if inputs else "No proposal inputs found."

read_proposal_inputs_tool = Tool.from_function(
    func=read_proposal_inputs,
    name="read_proposal_inputs",
    description="Reads the stored proposal inputs given a proposal ID."
)


def store_proposal_section(proposal_id, phase_name, output, agent_name = None, task_name = None, task_description = None):
    """Stores the output of a proposal processing phase and individual task output."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if agent_name is None:
        # Store in proposal_processing_phase (Master Table)
        cursor.execute("""
            INSERT INTO proposal_processing_phase (proposal_id, phase_name, content, reviewed)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(proposal_id, phase_name)
            DO UPDATE SET content=excluded.content, reviewed=0
        """, (proposal_id, phase_name, output, 0))
    else:
        # Store in proposal_task_output (Detail Table)
        cursor.execute("""
            INSERT INTO proposal_task_output (
                proposal_id, phase_name, output, agent_name, task_name,
                task_description
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (proposal_id, phase_name, output, agent_name, task_name, task_description))

    conn.commit()
    conn.close()
    return True


store_proposal_section_tool = Tool.from_function(
    func=store_proposal_section,
    name="store_proposal_section",
    description="Stores or updates a section of a proposal in the database."
)

def get_proposal_sections(proposal_id):
    """Retrieves proposal sections, ordered by phase and task creation time."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            pp.phase_name,
            pp.content AS phase_output,
            pto.task_name,
            pto.output AS task_output,
            pto.created_at
        FROM proposal_processing_phase pp
        LEFT JOIN proposal_task_output pto
            ON pp.proposal_id = pto.proposal_id AND pp.phase_name = pto.phase_name
        WHERE pp.proposal_id = ?
        ORDER BY pp.created_at, pto.created_at
    """, (proposal_id,))

    results = cursor.fetchall()
    conn.close()

    # Restructure the data
    ordered_data = {}
    for row in results:
        phase_name = row[0]
        phase_output = row[1]
        task_name = row[2]
        task_output = row[3]
        created_at = row[4]

        if phase_name not in ordered_data:
            ordered_data[phase_name] = {"phase_output": phase_output, "tasks": []}
        if task_name:  # Only add task if it exists (not None)
            ordered_data[phase_name]["tasks"].append({"task_name": task_name, "output": task_output, "created_at": created_at})

    return ordered_data

get_proposal_sections_tool = Tool.from_function(
    func=get_proposal_sections,
    name="get_proposal_sections",
    description="Retrieves all sections of a given proposal."
)

# ---- RAG Retriever (Using SQLite) ----
def rag_retriever(query_text):
    """Retrieves relevant past proposals based on input query."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT proposal_id, content FROM proposal_history WHERE content LIKE ?", ('%' + query_text + '%',))
    results = cursor.fetchall()
    conn.close()

    return [{"proposal_id": r[0], "summary": r[1][:300] + "..."} for r in results] if results else "No matching proposals found."

rag_retriever_tool = Tool.from_function(
    func=rag_retriever,
    name="rag_retriever",
    description="Retrieves past proposals similar to the given query."
)

# ---- Resource Allocation (Effort Model + Resource Pyramid) ----
def load_model():
    """Loads the trained effort estimation model."""
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)

effort_model = load_model()

def resource_allocation(project_type, category):
    """Predicts effort and resource needs based on project type and category."""
    estimated_effort = effort_model.predict([[project_type, category]])[0]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT manager_percentage, developer_percentage, qa_percentage FROM resource_pyramid WHERE project_type=? AND category=?", (project_type, category))
    pyramid = cursor.fetchone()
    conn.close()

    if not pyramid:
        return "Resource pyramid not found for given project type and category."

    return {
        "Total Effort (Hours)": estimated_effort,
        "Resource Allocation": {
            "Project Manager": round(estimated_effort * pyramid[0]),
            "Developers": round(estimated_effort * pyramid[1]),
            "QA Engineers": round(estimated_effort * pyramid[2])
        }
    }

resource_allocation_tool = Tool.from_function(
    func=resource_allocation,
    name="resource_allocation",
    description="Predicts effort and resource needs based on project type and category."
)

# ---- Pricing Analysis ----
def pricing_analysis(resources):
    """Estimates cost based on assigned resources."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, rate FROM resource_pricing")
    role_rates = dict(cursor.fetchall())
    conn.close()

    costs = {role: count * role_rates.get(role, 1000) for role, count in resources.items()}
    return {"Total Cost": sum(costs.values()), "Breakdown": costs}

pricing_analysis_tool = Tool.from_function(
    func=pricing_analysis,
    name="pricing_analysis",
    description="Calculates project pricing based on resource allocation."
)

# ---- Document Parser for Legal Compliance ----
def document_parser(contract_text):
    """Performs legal compliance checks on contract terms."""
    flagged_terms = ["penalty", "breach", "termination without notice"]
    flagged = [term for term in flagged_terms if term in contract_text.lower()]
    
    return {
        "Compliance Status": "Issues Found" if flagged else "Compliant",
        "Flagged Terms": flagged
    }

document_parser_tool = Tool.from_function(
    func=document_parser,
    name="document_parser",
    description="Performs legal compliance checks by identifying risky contract terms."
)

# To enable scrapping any website it finds during it's execution
tool = ScrapeWebsiteTool()

client_scrape = ScrapeWebsiteTool(website_url='https://www.example.com')
self_scrape = ScrapeWebsiteTool(website_url='https://www.example.com')


def ask_human_for_input(question: str) -> str:
    """
    Asks the human user for input via the Streamlit chat interface.
    This tool is called by an agent when it needs clarification or a decision.
    It signals the Streamlit app to prompt the user and waits for the response.
    """
    request_id = str(uuid.uuid4()) # Unique ID for this request
    st.session_state['human_input_request'] = {
        'id': request_id,
        'question': question,
        'response': None,
        'ready': False
    }

    # Signal Streamlit to ask the question (app.py will handle the display)
    # Wait for the response to be set by the Streamlit app
    while not st.session_state['human_input_request'].get('ready', False):
        time.sleep(1) # Wait for 1 second before checking again

    response = st.session_state['human_input_request'].get('response', "No response provided.")

    # Clear the request from session state
    del st.session_state['human_input_request']

    return response

human_feedback_tool = Tool(
    name="Human Feedback Tool",
    func=ask_human_for_input,
    description="Use this tool ONLY when you need clarification, a decision, or specific input directly from the human user to proceed with your task. Ask a clear question."
)

# ---- Final List of Tools ----
proposal_tools = [
    store_proposal_section_tool,
    get_proposal_sections_tool,
    rag_retriever_tool,
    resource_allocation_tool,
    pricing_analysis_tool,
    document_parser_tool,
    read_proposal_inputs_tool,
    client_scrape,
    self_scrape,
    human_feedback_tool 
]