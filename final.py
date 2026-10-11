# <TODO: Step 3 - Imports>
# Complete the imports for all the necessary components from the semantic_kernel library.
import asyncio
import json
import logging
import os
import re
import traceback

import pandas as pd
from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies import TerminationStrategy
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.functions import KernelArguments

load_dotenv()

# -----------------
# Logging Setup
# -----------------
# The logging setup below captures all agent interactions and saves them to 'logs/agent_chat.log'.
# 1. Create a dedicated logger for agent interactions.
agent_logger = logging.getLogger("semantic_kernel.agents")
agent_logger.setLevel(logging.DEBUG)

# 2. Prevent agent logs from propagating to other handlers (like console).
agent_logger.propagate = False

# 3. Create a file handler to write to 'agent_chat.log' in write mode.
os.makedirs("logs", exist_ok=True)
agent_chat_handler = logging.FileHandler("logs/agent_chat.log", mode='w')
agent_chat_handler.setLevel(logging.DEBUG)

# 4. Create a minimal formatter to log only the message content.
chat_formatter = logging.Formatter('%(asctime)s - %(name)s:%(message)s')
agent_chat_handler.setFormatter(chat_formatter)

# 5. Add the dedicated file handler to the agent logger.
agent_logger.addHandler(agent_chat_handler)

# 6. Function to log agent messages
def log_agent_message(content):
    try:
        agent_logger.info(f"Agent: {content.role} - {content.name or '*'}: {content.content}")
    except Exception:
        agent_logger.exception("Failed to write agent message to log")

# -----------------
# Environment Setup
# -----------------
# <TODO: Step 2 - Environment Setup>
# Load the API key and endpoint URL from the .env file.

API_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_ENDPOINT = os.getenv("URL")
if AZURE_ENDPOINT:
    AZURE_ENDPOINT = AZURE_ENDPOINT.removesuffix("/openai/v1").rstrip("/")
API_VERSION = os.getenv("API_VERSION")
CHAT_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
MAX_CODE_ATTEMPTS = int(os.getenv("MAX_CODE_ATTEMPTS", "3"))
DEBUG = os.getenv("WORKFLOW_DEBUG") == "1"


# -----------------
# Kernel and Chat Service
# -----------------
# <TODO: Step 3 - Kernel Initialization>
# Initialize the Kernel, define the AzureChatCompletion service, and add it to the kernel.
kernel = Kernel()
chat_service = AzureChatCompletion(
    api_key=API_KEY,
    endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION,
    deployment_name=CHAT_DEPLOYMENT_NAME,
)
kernel.add_service(chat_service)


# -----------------
# Helper Functions
# -----------------
# <TODO: Step 4 - Implement Supporting Logic>
# Implement the logic for each of the helper functions below.

def load_quality_instructions(file_path):
    """
    Loads instructional text from a file within the 'specs' directory.

    This function constructs the full path to the file, reads its content,
    and processes it into a list of non-empty, stripped lines.

    Args:
        file_path (str): The name of the file in the 'specs' directory.

    Returns:
        list[str]: A list of strings, where each string is a line of instruction.
                   Returns an empty list if the file does not exist.
    """
    path = os.path.join("specs", file_path)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_reports_instructions(file_path):
    """
    Loads report generation instructions from a file within the 'specs' directory.

    Args:
        file_path (str): The name of the file in the 'specs' directory.

    Returns:
        list[str]: A list of strings for building the report. Returns an
                   empty list if the file does not exist.
    """
    return load_quality_instructions(file_path)


def load_logs(file_path):
    """
    Loads agent interaction logs from a file within the 'logs' directory.

    Args:
        file_path (str): The name of the log file in the 'logs' directory.

    Returns:
        list[str]: A list of log entries. Returns an empty list if the file
                   does not exist.
    """
    path = os.path.join("logs", file_path)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_csv_name():
    """
    Interactively prompts the user to select a CSV file from the 'data' directory.

    It lists all available .csv files and asks for a numerical selection.

    Returns:
        str: The relative path to the selected CSV file (e.g., 'data/my_file.csv').
    """
    data_dir = "data"
    csv_files = sorted(
        os.path.join(data_dir, name)
        for name in os.listdir(data_dir)
        if name.lower().endswith(".csv")
    )

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir!r}.")

    print("Available CSV files:")
    for idx, file_path in enumerate(csv_files, start=1):
        print(f"{idx}. {os.path.basename(file_path)}")

    while True:
        try:
            selection = input("Select a CSV file by number: ").strip()
            choice = int(selection)
            if 1 <= choice <= len(csv_files):
                return csv_files[choice - 1]
            print("Invalid selection. Please choose a listed number.")
        except ValueError:
            print("Please enter a numeric value.")


def load_csv_file(file_path):
    """
    Reads a CSV file and converts its entire content into a single string.

    The CSV data is flattened into a list and then joined by ', '.

    Args:
        file_path (str): The path to the CSV file to load.

    Returns:
        str: A single string containing all the data from the CSV file.
    """
    import pandas as pd

    df = pd.read_csv(file_path)
    flattened = [str(value) for row in df.to_numpy().tolist() for value in row]
    return ", ".join(flattened)

class PythonExecutor:
    """
    A safe executor for dynamically generated Python code strings.

    This class is designed to run code provided by an AI agent in a controlled
    manner. It includes a retry mechanism and captures execution errors.
    """
    def __init__(self, max_attempts=3):
        self.max_attempts = max_attempts

    def run(self, code):
        """
        Executes a string of Python code using the exec() function.

        Args:
            code (str): The Python code to execute.

        Returns:
            tuple[bool, str | None]: A tuple containing:
                - A boolean indicating if the execution was successful.
                - The error traceback as a string if an exception occurred,
                  otherwise None.
        """
        if not code.strip():
            return False, "No visualization code was generated."

        try:
            exec(compile(code, "<generated visualization>", "exec"), {"__name__": "__main__"})
        except Exception:
            return False, traceback.format_exc()

        return True, None

def save_final_report(report, path='artifacts/final_report.md'):
    """
    Saves the generated final report to a markdown file.

    Args:
        report (str): The content of the report to be saved.
        path (str, optional): The file path for the saved report.
                              Defaults to 'artifacts/final_report.md'.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(report)


# -----------------
# Agent Instructions
# -----------------
# <TODO: Step 5 - Build the Agents and Teams>
# 1. Complete the AGENT_CONFIG with detailed prompts for each agent.
data_quality_instructions = '\n'.join(load_quality_instructions("Data_Quality_Instructions.txt"))
report_instructions = '\n'.join(load_reports_instructions("Report_Instructions.txt"))

AGENT_CONFIG = {
    "PythonExecutorAgent": """Generate runnable Python code that visualizes the original and cleaned datasets.
        Use matplotlib to plot both datasets as line series on one chart: original data in blue and cleaned data in green.
        Create the artifacts directory if it does not exist and save the chart to artifacts/data_visualization.png.
        Use the data and column names provided in the conversation. Output only raw Python code, with no markdown fences,
        explanations, or comments.""",
    "DataCleaning": f"""Act as a Data Cleaning Assistant. Inspect the provided dataset and follow these rules:
        {data_quality_instructions}
        Before cleaning, present a concise cleaning plan that identifies date-column handling and the method for detecting
        and removing outliers. Work step by step: inspect the columns and types, state the plan, flag the outliers, then
        remove them. After the plan, clean the data without waiting for a reply. Preserve the dataset's structure and do not
        invent or silently discard columns. Finish with a line "Cleaned dataset:" followed by the cleaned rows as a JSON
        array of row objects, for example [{{"Date": "2025-09-01", "Value": 542}}].""",
    "DataStatistics": """        Act as a Data Statistics Assistant. Calculate descriptive statistics for the cleaned dataset only,
        including mean, median, standard deviation, minimum, and maximum where applicable. When given data, output only the
        statistical description, with no commentary or recommendations. Example output:
        mean: 527.81
        median: 519.5
        std_dev: 39.58
        min: 488
        max: 621""",
    "AnalysisChecker": f"""        Act as a Data Validation Auditor. Validate the data cleaning and analysis using these rules:
        {data_quality_instructions}
        Verify that identified outliers were removed before descriptive statistics were calculated, and confirm the
        statistics use only the cleaned dataset. Do not approve if the evidence is incomplete. Return valid JSON with the
        fields required by the rules; set title to Approved or Failed and explain any failure clearly.""",
    "ReportGenerator": f"""        Act as a Report Generator. Synthesize the dataset cleaning, removed outliers, descriptive statistics,
        validation results, and visualization into a complete Markdown report. Follow this required structure and fill in
        all sections using evidence from the conversation:
        {report_instructions}""",
    "ReportChecker": f"""        Act as a Report Validation Auditor. Check that the final report is complete and factually consistent
        with the analysis, and that every required section, table, and visualization reference is present. Validate it
        against these report rules:
        {report_instructions}
        Return Approved only when all checks pass. Otherwise, report each missing or inaccurate item and request a correction.""",
}

AGENT_TEMPERATURES = {
    "PythonExecutorAgent": 0.1,
    "DataCleaning": 0.7,
    "DataStatistics": 0.5,
    "AnalysisChecker": 0.2,
    "ReportGenerator": 1.0,
    "ReportChecker": 0.2,
}


# -----------------
# Agent Factory
# -----------------
# <TODO: Step 5 - Build the Agents and Teams>
# 2. Implement the agent factory function.
def create_agent(name, instructions, service, settings=None):
    """Factory function to create a new ChatCompletionAgent."""
    arguments = KernelArguments(settings=settings) if settings is not None else None
    return ChatCompletionAgent(
        kernel=kernel,
        name=name,
        instructions=instructions,
        service=service,
        arguments=arguments,
    )


# -----------------
# Termination Strategy
# -----------------
# A custom termination strategy that stops after user approval.
def is_approval(text):
    text = (text or "").strip().lower().lstrip("*#> \n")
    return text.startswith("approved") or re.search(r'"title"\s*:\s*"approved"', text) is not None


class ApprovalTerminationStrategy(TerminationStrategy):
    """A custom termination strategy that stops after user approval."""
    async def should_agent_terminate(self, agent, history):
        return is_approval(history[-1].content)


# -----------------
# Agent Instantiation
# -----------------
# <TODO: Step 5 - Build the Agents and Teams>
# 3. Instantiate each agent with the correct name, prompt, and temperature setting.
def build_agent(name):
    settings = AzureChatPromptExecutionSettings(temperature=AGENT_TEMPERATURES[name])
    return create_agent(name, AGENT_CONFIG[name], chat_service, settings)


python_agent = build_agent("PythonExecutorAgent")
cleaning_agent = build_agent("DataCleaning")
stats_agent = build_agent("DataStatistics")
checker_agent = build_agent("AnalysisChecker")
report_agent = build_agent("ReportGenerator")
report_checker_agent = build_agent("ReportChecker")


# -----------------
# Group Chats
# -----------------
# <TODO: Step 5 - Build the Agents and Teams>
# 4. Create the three agent group chats.
analysis_chat = AgentGroupChat(
    agents=[cleaning_agent, stats_agent, checker_agent],
    termination_strategy=ApprovalTerminationStrategy(agents=[checker_agent], maximum_iterations=6),
)
code_chat = AgentGroupChat(agents=[python_agent])
report_chat = AgentGroupChat(
    agents=[report_agent, report_checker_agent],
    termination_strategy=ApprovalTerminationStrategy(agents=[report_checker_agent], maximum_iterations=6),
)


# -----------------
# Main Workflow
# -----------------
# <TODO: Step 6 - Orchestrate the Main Workflow>
# Implement the main workflow logic, following the sequence described in the instructions.
async def main():
    """The main entry point for the agentic workflow."""
    async def collect_messages(chat, agent=None):
        messages = []
        async for message in chat.invoke(agent):
            messages.append(message)
            log_agent_message(message)
            if message.content:
                print(f"\n[{message.name or message.role}]\n{message.content}")
        return messages

    # 1. Load the CSV data.
    try:
        csv_path = get_csv_name()
        original_df = pd.read_csv(csv_path)
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        print(f"Could not load a CSV file: {exc}")
        return
    if original_df.empty:
        print(f"{csv_path} has no data rows; nothing to analyze.")
        return
    original_json = original_df.to_json(orient="records", date_format="iso")
    initial_prompt = (
        f"Analyze and clean the CSV file {os.path.basename(csv_path)!r}.\n"
        "Present the cleaning plan first, then proceed with cleaning, calculate statistics only after cleaning, "
        "and validate the results. Do not wait for another user response during analysis. Return the cleaned dataset "
        "from the DataCleaning agent as a valid JSON array of row objects.\n\n"
        f"CSV columns: {', '.join(str(column) for column in original_df.columns)}\n"
        f"Original dataset as JSON: {original_json}"
    )

    # 2. Invoke the analysis chat.
    await analysis_chat.add_chat_message(initial_prompt)
    analysis_messages = await collect_messages(analysis_chat)

    # 3. Get human approval.
    approval = input("Continue to visualization and report generation? Type 'yes' to proceed: ").strip().lower()
    agent_logger.info(f"Human approval response: {approval!r}")
    if approval != "yes":
        print("Workflow stopped; no deliverables were generated.")
        return

    # 4. Save the cleaned data.
    cleaned_message = next(
        (
            message
            for message in reversed(analysis_messages)
            if message.name == cleaning_agent.name and message.content
        ),
        None,
    )
    if cleaned_message is None:
        raise RuntimeError("The analysis chat did not return cleaned data from the DataCleaning agent.")

    cleaned_text = cleaned_message.content.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        cleaned_data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        cleaned_marker = cleaned_text.lower().rfind("cleaned dataset")
        search_from = cleaned_marker if cleaned_marker >= 0 else 0
        array_start = cleaned_text.find("[", search_from)
        if array_start < 0:
            raise ValueError("The DataCleaning agent response does not contain a cleaned-data JSON array.") from exc
        try:
            cleaned_data, _ = json.JSONDecoder().raw_decode(cleaned_text[array_start:])
        except json.JSONDecodeError as array_exc:
            raise ValueError("The cleaned-data section is not a valid JSON array.") from array_exc

    if not isinstance(cleaned_data, list) or not all(isinstance(row, dict) for row in cleaned_data):
        raise ValueError("The cleaned dataset must be a JSON array of row objects.")

    cleaned_data_path = "data-cleaned.json"
    with open(cleaned_data_path, "w", encoding="utf-8") as cleaned_file:
        json.dump(cleaned_data, cleaned_file, indent=2, ensure_ascii=False)

    # 5. Invoke the code chat to generate visualization code.
    os.makedirs("artifacts", exist_ok=True)
    code_prompt = (
        "Generate a runnable Python script using matplotlib. Plot the original data in blue and cleaned data in green "
        "as line series on one chart, and save it to artifacts/data_visualization.png. The datasets are JSON arrays "
        "of row objects; use their shared numeric columns. Create artifacts if needed. Return only raw Python code, "
        "without markdown fences, explanations, or comments.\n\n"
        f"Original dataset JSON:\n{original_json}\n\n"
        f"Cleaned dataset JSON:\n{json.dumps(cleaned_data, ensure_ascii=False)}"
    )
    await code_chat.add_chat_message(code_prompt)
    executor = PythonExecutor(max_attempts=MAX_CODE_ATTEMPTS)
    visualization_path = os.path.join("artifacts", "data_visualization.png")
    visualization_code = None

    # 6. Execute the generated code and request fixes after failures.
    for attempt in range(executor.max_attempts):
        code_messages = await collect_messages(code_chat, python_agent)
        generated_message = next(
            (
                message
                for message in reversed(code_messages)
                if message.name == python_agent.name and message.content
            ),
            None,
        )
        if generated_message is None:
            raise RuntimeError("The code chat did not return visualization code.")

        visualization_code = generated_message.content.strip()
        if visualization_code.startswith("```"):
            visualization_code = visualization_code.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        succeeded, execution_error = executor.run(visualization_code)
        agent_logger.info(f"Code attempt {attempt + 1}/{executor.max_attempts}: {'succeeded' if succeeded else 'failed'}")
        if DEBUG and execution_error:
            print(f"[debug] attempt {attempt + 1} error:\n{execution_error}")
        if succeeded and os.path.isfile(visualization_path):
            break

        if succeeded:
            execution_error = f"The script completed but did not create {visualization_path}."
        if attempt + 1 == executor.max_attempts:
            raise RuntimeError(
                f"Visualization code failed after {executor.max_attempts} attempts:\n{execution_error}"
            )

        await code_chat.add_chat_message(
            "The previous visualization script failed. Fix it and return only the complete raw Python script.\n"
            f"Execution error:\n{execution_error}"
        )

    # 7. Save the successfully executed visualization script.
    script_path = os.path.join("artifacts", "data_visualization_code.py")
    with open(script_path, "w", encoding="utf-8") as script_file:
        script_file.write(visualization_code)

    # 8. Invoke the report chat with the complete interaction log.
    interaction_log = "\n".join(load_logs("agent_chat.log"))
    await report_chat.add_chat_message(
        "Generate and validate the final Markdown report using the complete agent interaction log below. "
        "Include the generated visualization and do not omit required report sections.\n\n"
        f"Agent interaction log:\n{interaction_log}"
    )
    report_messages = await collect_messages(report_chat)
    checker_messages = [
        message.content.strip()
        for message in report_messages
        if message.name == report_checker_agent.name and message.content
    ]
    if not checker_messages or not is_approval(checker_messages[-1]):
        raise RuntimeError("The ReportChecker did not approve the final report.")

    # 9. Save the final Markdown report.
    final_report = next(
        (
            message.content
            for message in reversed(report_messages)
            if message.name == report_agent.name and message.content
        ),
        None,
    )
    if final_report is None:
        raise RuntimeError("The report chat did not return a report from the ReportGenerator agent.")
    save_final_report(final_report)
    print("Workflow complete. Cleaned data, visualization, and report were saved.")


# -----------------
# Main Execution
# -----------------
if __name__ == "__main__":
    asyncio.run(main())