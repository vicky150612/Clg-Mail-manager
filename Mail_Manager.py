from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv
from datetime import datetime, timezone

from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

load_dotenv()


# ---------------- AgentState ----------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# ---------------- Google Tasks Service ----------------
SCOPES = ["https://www.googleapis.com/auth/tasks"]


def get_tasks_service():
    creds = None
    token_path = "token.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("tasks", "v1", credentials=creds)


# ---------------- Helpers ----------------
def format_due_date(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp)
    if dt.tzinfo is None:  # assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


# ---------------- TOOLS ----------------
@tool
def read_tasks() -> str:
    """Read tasks from Google Tasks (default task list)."""
    try:
        service = get_tasks_service()
        results = service.tasks().list(tasklist="@default", maxResults=10).execute()
        items = results.get("items", [])
        if not items:
            return "No tasks found."
        return "\n".join(
            [f"{task['title']} - {task.get('status', 'unknown')}" for task in items]
        )
    except Exception as ex:
        return f"Error reading tasks: {ex}"


@tool
def create_task(task_name: str, status: str, description: str, timestamp: str) -> str:
    """
    Create a task in Google Tasks if it does not already exist.
    """
    try:
        service = get_tasks_service()
        due_time = format_due_date(timestamp)

        # Fetch 100 tasks and check for duplicates
        existing_tasks = (
            service.tasks()
            .list(tasklist="@default", maxResults=100)
            .execute()
            .get("items", [])
        )
        for task in existing_tasks:
            if task.get("title", "").strip().lower() == task_name.strip().lower():
                return f"Task '{task_name}' already exists. Skipping creation."

        task_body = {
            "title": task_name,
            "notes": f"{status}: {description}",
            "due": due_time,
        }

        service.tasks().insert(tasklist="@default", body=task_body).execute()
        return f"Task '{task_name}' created successfully."
    except Exception as ex:
        return f"Error creating task: {ex}"


@tool
def edit_task(
    task_name: str, new_status: str, new_description: str, new_timestamp: str
) -> str:
    """
    Edit a task in Google Tasks.
    """
    try:
        service = get_tasks_service()
        tasks = (
            service.tasks()
            .list(tasklist="@default", q=task_name)
            .execute()
            .get("items", [])
        )
        if not tasks:
            return f"Task '{task_name}' not found."

        task_obj = tasks[0]
        due_time = format_due_date(new_timestamp)

        task_obj.update(
            {
                "title": task_name,
                "notes": f"{new_status}: {new_description}",
                "due": due_time,
            }
        )

        service.tasks().update(
            tasklist="@default", task=task_obj["id"], body=task_obj
        ).execute()
        return f"Task '{task_name}' updated successfully."
    except Exception as ex:
        return f"Error editing task: {ex}"


@tool
def remove_task(task_name: str) -> str:
    """
    Remove a task from Google Tasks.
    """
    try:
        service = get_tasks_service()
        tasks = (
            service.tasks()
            .list(tasklist="@default", q=task_name)
            .execute()
            .get("items", [])
        )
        if not tasks:
            return f"Task '{task_name}' not found."

        service.tasks().delete(tasklist="@default", task=tasks[0]["id"]).execute()
        return f"Task '{task_name}' removed successfully."
    except Exception as ex:
        return f"Error removing task: {ex}"


# ---------------- SYSTEM PROMPT ----------------
SYSTEM_PROMPT = f"""
You are an AI Mail Agent that manages Google Tasks.

When you receive an email, analyze it and determine what actions need to be taken:

1. If the email mentions a deadline, meeting, or task that needs to be tracked, create a new task
2. If the email refers to updating an existing task, use the edit_task function
3. If the email mentions canceling or completing a task, use the remove_task function
4. If you need to check existing tasks first, use the read_tasks function

Use the available tools to manage tasks appropriately. Extract relevant information like:
- Task name/title
- Status (pending, in-progress, completed, etc.)
- Description/notes
- Due date/time (if date is ambiguous, assume the nearest possible date to the current date)

Always provide a summary of what actions were taken.
Current date and time is: {datetime.now(timezone.utc).isoformat()}
"""

# ---------------- TOOLS AND MODEL SETUP ----------------
tools = [read_tasks, create_task, edit_task, remove_task]

model = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools(tools)


# ---------------- GRAPH NODES ----------------
def model_call(state: AgentState) -> AgentState:
    system_prompt = SystemMessage(content=SYSTEM_PROMPT)
    response = model.invoke([system_prompt] + state["messages"])
    return {"messages": [response]}


def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"


# ---------------- GRAPH SETUP ----------------
graph = StateGraph(AgentState)
graph.add_node("mail_agent", model_call)

tool_node = ToolNode(tools=tools)
graph.add_node("tools", tool_node)

graph.set_entry_point("mail_agent")

graph.add_conditional_edges(
    "mail_agent",
    should_continue,
    {
        "continue": "tools",
        "end": END,
    },
)
graph.add_edge("tools", END)

app = graph.compile()


# ---------------- EMAIL ANALYSIS ----------------
def analyse_email_process_task(email: str):
    inputs = {
        "messages": [
            (
                "user",
                f"Please analyze this email and manage tasks accordingly:\n\n{email}",
            )
        ]
    }

    messages = []
    for s in app.stream(inputs, stream_mode="values"):
        messages = list(s["messages"])

    final_response = messages[-1].content if messages else "No response generated"

    return {
        "final_response": final_response,
        "all_messages": messages,
        "execution_complete": True,
    }


# ---------------- MAIN ----------------
if __name__ == "__main__":
    email = """
    Dear all,
    U have a physics quiz scheduled on friday i.e 12th.
    Regards,
    B ashok
    """

    print("📩 Analyzing Email:")
    print(email)
    print("\n" + "=" * 50)

    response = analyse_email_process_task(email)

    print("\n📋 Final Response:")
    print(response["final_response"])

    print("\n📜 Execution Details:")
    print(f"Messages processed: {len(response['all_messages'])}")
    print(f"Tool calls made: {response.get('tool_calls_made', 'Unknown')}")
    print(f"Execution complete: {response['execution_complete']}")

    print("\n🗨️ Conversation Messages:")
    for i, msg in enumerate(response["all_messages"], 1):
        print(f"\n--- Message {i} ---")
        print(f"Type: {type(msg).__name__}")
        print(f"Content:\n{getattr(msg, 'content', str(msg))}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"Tool Calls: {msg.tool_calls}")

    print("\n" + "=" * 50)
    print("🔍 Detailed Stream Output:")

    print("\n✅ Execution Finished")
