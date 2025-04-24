# proposal_team.py
import yaml
import os
from crewai import Agent, Task, Crew, Process 
# from crewai import LLM, Process
from crewai.memory import LongTermMemory, ShortTermMemory, EntityMemory
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage
from crewai.memory.storage.rag_storage import RAGStorage
from langchain_google_genai import ChatGoogleGenerativeAI # Using Gemini directly via Langchain

# Import the specific tools needed, including the new one
from proposal_tools import (
    resource_allocation_tool, rag_retriever_tool, pricing_analysis_tool,
    document_parser_tool, read_proposal_inputs_tool, self_scrape, client_scrape,
    human_feedback_tool 
)
from callbacks import callback_function

# Load YAML Configurations
def load_yaml_config(file_path):
    """Loads YAML config files."""
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

AGENTS_CONFIG = load_yaml_config("config/agents.yaml")["agents"]
TASKS_CONFIG = load_yaml_config("config/tasks.yaml")["tasks"]
# Load inputs from the new file
INPUTS_CONFIG = load_yaml_config("config/inputs.yaml")["required_inputs"]

llm_config = load_yaml_config("config/llm.yaml")["llm"][0]

# --- LLM Configuration ---
os.environ['GOOGLE_API_KEY'] = os.environ.get('GEMINI_API_KEY', 'YOUR_API_KEY_HERE') 
llm = ChatGoogleGenerativeAI(model="gemini-pro", # or gemini-1.5-flash, etc.
                           verbose=True,
                           temperature=0.5 # Adjust temperature as needed
                           )
# Or if using Ollama via Langchain integration (example)
# from langchain_community.llms import Ollama
# llm = Ollama(model=llm_config["name"], base_url=llm_config["base_url"])


# Memory Configuration
def configure_memory():
    """Configures memory for CrewAI"""
    return {
        "long_term_memory": LongTermMemory(storage=LTMSQLiteStorage(db_path="./db/long_term_memory_storage.db")),
        "short_term_memory": ShortTermMemory(storage=RAGStorage(
            embedder_config={"provider": "ollama", "base_url": os.getenv('OLLAMA_HOST'), "config": {"model": 'nomic-embed-text'}},
            type="short_term", path="./db/")),
        "entity_memory": EntityMemory(storage=RAGStorage(
            embedder_config={"provider": "ollama", "base_url": os.getenv('OLLAMA_HOST'), "config": {"model": 'nomic-embed-text'}},
            type="short_term", path="./db/"))
    }

memory_config = configure_memory()

# --- Create Agents ---
agents_dict = {}
for agent_cfg in AGENTS_CONFIG:
    # Dynamically create the list of tool functions
    agent_tools = []
    for tool_name in agent_cfg.get("tools", []): # Use .get for safety
        if tool_name in globals():
             # Add human_feedback_tool explicitly if agent might need it
            if tool_name == "human_feedback_tool":
                 agent_tools.append(human_feedback_tool)
            elif tool_name == "client_scrape": # Specific handling for scrape tools
                 agent_tools.append(client_scrape)
            elif tool_name == "self_scrape":
                 agent_tools.append(self_scrape)
            else:
                 agent_tools.append(globals()[tool_name]) # Add other tools
        else:
            print(f"Warning: Tool '{tool_name}' not found for agent '{agent_cfg['name']}'.")

    # Add human_feedback_tool to agents that might logically need it,
    # like Account Manager, Proposal Owner, Financial Analyst, Legal Analyst
    if agent_cfg["name"] in ["Account Manager", "Proposal Owner", "Financial Analyst", "Legal Analyst"]:
         if human_feedback_tool not in agent_tools:
              agent_tools.append(human_feedback_tool)

    agents_dict[agent_cfg["name"]] = Agent(
        name=agent_cfg["name"],
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"],
        tools=agent_tools, # Use the dynamically created list
        verbose=True,
        llm=llm,
        allow_delegation=False, 
        # human_input=True
    )

# --- Create Tasks ---
tasks_dict = {}
for task_cfg in TASKS_CONFIG:
    agent_name = task_cfg.get("agent")
    if not agent_name or agent_name not in agents_dict:
        print(f"Error: Agent '{agent_name}' not found for task '{task_cfg['name']}'. Skipping task.")
        continue

    agent = agents_dict[agent_name]
    # Build dependencies based on the 'context' list in tasks.yaml
    dependencies = [tasks_dict[dep_name] for dep_name in task_cfg.get("context", []) if dep_name in tasks_dict]

    needs_human_input = "human feedback tool" in task_cfg["description"].lower() or task_cfg["name"] == "Final Review"

    tasks_dict[task_cfg["name"]] = Task(
        # name=task_cfg["name"], # CrewAI Task doesn't take 'name' as argument
        description=task_cfg["description"],
        expected_output=task_cfg["expected_output"],
        agent=agent,
        context=dependencies, 
        output_file=f"{task_cfg['name']}.md",
        ask_human_input = needs_human_input
    )

# --- Create Crews ---
proposal_analysis_crew = Crew(
    agents=[agents_dict["Business Analyst"], agents_dict["Account Manager"], agents_dict["Proposal Owner"]], # Adjusted order based on likely flow
    tasks=[tasks_dict["Business Review"], tasks_dict["Bid Strategy"], tasks_dict["Proposal Kickoff"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,    
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/analysis.txt",
    share_crew=True
)

proposal_solution_crew = Crew(
    agents=[agents_dict["Solution Architect"], agents_dict["Project Manager"], agents_dict["Proposal Owner"]],
    tasks=[tasks_dict["Solution Design"], tasks_dict["Implementation Plan"], tasks_dict["Approach"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,    
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/approach.txt",
    share_crew=True
)

proposal_drafting_crew = Crew(
    agents=[agents_dict["Financial Analyst"], agents_dict["Legal Analyst"], agents_dict["Proposal Writer"], agents_dict["Proposal Owner"]],
    tasks=[tasks_dict["Financial Analysis"], tasks_dict["Legal Review"], tasks_dict["Draft Proposal"], tasks_dict["Final Review"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,    
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/draft.txt",
    share_crew=True
)

if __name__ == "__main__":
    proposal_id = 'test-human-input' # Example ID
    collected_inputs = {
        'proposal_id': proposal_id,
        'client_website': 'https://www.bankofindia.co.in', # Example
        'applicant_website': 'https://www.tcs.com', # Example
        'document_list': [] # Add actual file paths if testing parsing
    }

    print("--- Kicking off Analysis Crew ---")
    analysis_result = proposal_analysis_crew.kickoff(inputs=collected_inputs)
    print("\n--- Analysis Crew Result ---")
    print(analysis_result)

    print("\n--- Kicking off Solution Crew ---")
    solution_result = proposal_solution_crew.kickoff(inputs=collected_inputs)
    print("\n--- Solution Crew Result ---")
    print(solution_result)

    print("\n--- Kicking off Drafting Crew ---")
    drafting_result = proposal_drafting_crew.kickoff(inputs=collected_inputs)
    print("\n--- Drafting Crew Result ---")
    print(drafting_result)