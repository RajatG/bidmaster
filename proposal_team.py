import yaml
import os
from crewai import Agent, Task, Crew, LLM, Process
from typing import List, Optional, Dict, Any
from crewai.memory import LongTermMemory, ShortTermMemory, EntityMemory
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage
from crewai.memory.storage.rag_storage import RAGStorage
from proposal_tools import (
    resource_allocation_tool, rag_retriever_tool, pricing_analysis_tool,
    document_parser_tool, read_proposal_inputs_tool, self_scrape, client_scrape
)
from callbacks import callback_function


# Load YAML Configurations
def load_yaml_config(file_path):
    """Loads YAML config files."""
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

AGENTS_CONFIG = load_yaml_config("config/agents.yaml")["agents"]
TASKS_CONFIG = load_yaml_config("config/tasks.yaml")["tasks"]
llm = load_yaml_config("config/llm.yaml")["llm"][0]

api_key = os.getenv("GEMINI_API_KEY")

# LLM Configuration
#llm = LLM(model="huggingface/deepseek-ai/DeepSeek-R1"
#llm = LLM(model=llm["name"], base_url=llm["base_url"], timeout=1000)
llm = LLM(model=llm["name"])

class ProposalTask:
    def __init__(
        self,
        name: str,
        description: str,
        expected_output: str,
        agent: Agent,
        dependencies: Optional[List["Task"]] = None,
        input_fields: Optional[Dict[str, Dict[str, str]]] = None,  # Changed to Dict[str, Dict]
    ):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.dependencies = dependencies or []
        self.input_fields = input_fields or {}  # Store input field definitions
        self.result: Optional[str] = None
        
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

# Create Agents
agents_dict = {}
for agent in AGENTS_CONFIG:
        tools = [globals()[tool_name] for tool_name in agent["tools"]]
        agents_dict[agent["name"]] = Agent(
        name=agent["name"],
        role=agent["role"],
        goal=agent["goal"],
        backstory=agent["backstory"],
        tools=tools,
        verbose=True,
        llm=llm,
        output_format="markdown" 
    )

# First, create CustomTask instances
proposal_tasks_dict = {}
for task in TASKS_CONFIG:
    agent = agents_dict[task["agent"]]
    dependencies = [proposal_tasks_dict[dep] for dep in task.get("context", [])]
    proposal_tasks_dict[task["name"]] = ProposalTask(
        name=task["name"],
        description=task["description"],
        expected_output=task["expected_output"],
        agent=agent,
        dependencies=dependencies,
        input_fields=task.get("input_fields", {})
    )
    
 
# Create Tasks
tasks_dict = {}
for task in TASKS_CONFIG:
        agent = agents_dict[task["agent"]]
        dependencies = [tasks_dict[dep] for dep in getattr(task, "context", [])]
        tasks_dict[task["name"]] = Task(
        name=task["name"],
        description=task["description"],
        expected_output=task["expected_output"],
        agent=agent,    
        dependencies=dependencies,
        input_fields = task.input_fields if hasattr(task, "input_fields") else {},
        output_file=f"{task['name']}.md" 
    )   

proposal_crew = Crew(
    agents=list(agents_dict.values()),
    tasks=list(tasks_dict.values()),
    process=Process.sequential,
    verbose=True,
    max_rpm=10,
    task_callback=callback_function,
    **memory_config,
    output_log_file = True
)

# **Proposal Analysis Crew**
proposal_analysis_crew = Crew(
    agents=[agents_dict["Proposal Owner"], agents_dict["Business Analyst"], agents_dict["Account Manager"]],
    tasks=[tasks_dict["Business Review"], tasks_dict["Bid Strategy"],tasks_dict["Proposal Kickoff"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/analysis.txt"
)

# **Proposal Solution Crew**
proposal_solution_crew = Crew(
    agents=[agents_dict["Proposal Owner"], agents_dict["Solution Architect"], agents_dict["Project Manager"]],
    tasks=[tasks_dict["Solution Design"], tasks_dict["Implementation Plan"], tasks_dict["Approach"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/approach.txt"
)

# **Proposal Finalization Crew**
proposal_drafting_crew = Crew(
    agents=[agents_dict["Proposal Owner"], agents_dict["Financial Analyst"], agents_dict["Legal Analyst"], agents_dict["Proposal Writer"]],
    tasks=[tasks_dict["Financial Analysis"], tasks_dict["Legal Review"], tasks_dict["Draft Proposal"], tasks_dict["Final Review"]],
    process=Process.sequential,
    verbose=True,
    #max_rpm=10,
    task_callback=callback_function,
    **memory_config,
    output_log_file = "./logs/draft.txt"
)

proposal_test_crew = Crew(
    agents=[agents_dict["Proposal Owner"], agents_dict["Business Analyst"], agents_dict["Account Manager"]],
    tasks=[tasks_dict["Business Review"]],
    #process=Process.sequential,
    verbose=True,
    #max_rpm=10,
    task_callback=callback_function,
    **memory_config,
    output_log_file = "/logs/temp.txt"
)

if __name__ == "__main__":
    proposal_id = '1cb35a6f-4d97-4649-ad73-7db96b8e53ad'
    upload_directory = f"uploads/{proposal_id}/"
    file_paths = []
    if os.path.exists(upload_directory) and os.listdir(upload_directory):
        for file in os.listdir(upload_directory):
            file_path = os.path.join(upload_directory, file)
            file_paths.append(file_path)
        inputs = {'proposal_id': proposal_id, 'document_list': file_paths}
        proposal_test_crew.kickoff(inputs=inputs)
    else:
        print(f"Directory {upload_directory} does not exist or is empty.")
