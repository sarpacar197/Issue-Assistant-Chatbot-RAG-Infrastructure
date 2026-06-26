import operator
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent_core import Agent, model, issue_open, similar_document, rootcause_agent

ISSUE_PROMPT = (
    "You are the issue creation assistant. Use the issue_open tool to create an issue. "
    "The following fields are REQUIRED for issue_open: title, description, priority, assignee_name. "
    "If the user hasn't provided any of these, ASK the user FOR EACH MISSING ITEM INDIVIDUALLY."
    "Don't create any fields yourself. Don't call issue_open until all the information is complete."
)

issue_agent = Agent(model, [issue_open], system=ISSUE_PROMPT)

class OrchestratorState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    route : str
    draft : str

def supervisor(state : OrchestratorState):
    sys = ("Classify the user's message. Write ONLY one word:\n"
           "issue     -> issue open/record generation\n"
           "rootcause -> Asking for the cause/solution to a problem, requesting analysis.\n"
           "other     -> everything else")
    out = model.invoke([SystemMessage(content=sys)] + state['messages'])
    k = out.content.strip().lower()
    route = "issue" if "issue" in k else "rootcause" if "rootcause" in k else "other"
    print(f"supervisor: {route}")
    return {"route": route}

def run_issue(state: OrchestratorState):
    res = issue_agent.graph.invoke({"messages": state['messages']})
    return {"draft": res['messages'][-1].content}

def run_other(state: OrchestratorState):
    sys = ("You are a helpful assistant. Engage in normal conversation with the user and answer their questions. "
           "Remind them that they can open an issue if they want to. Write in Turkish.")
    out = model.invoke([SystemMessage(content=sys)] + state["messages"])
    return {"messages": [out]}

def run_rootcause(state : OrchestratorState):
    res = rootcause_agent.graph.invoke({"messages": state["messages"]})
    return {"draft" : res["messages"][-1].content}

def summarizor(state: OrchestratorState):
    sys = "Convert the raw result below into a short, clear, and polite response for the user. Write it in Turkish."
    out = model.invoke([SystemMessage(content=sys), HumanMessage(content=state['draft'])])
    return {"messages": [AIMessage(content=out.content)]}


g = StateGraph(OrchestratorState)
g.add_node("supervisor", supervisor)
g.add_node("issue", run_issue)
g.add_node("rootcause", run_rootcause)
g.add_node("other", run_other)
g.add_node("summarizor", summarizor)

g.set_entry_point("supervisor")
g.add_conditional_edges("supervisor", lambda s: s["route"],{"issue": "issue", "rootcause": "rootcause", "other": "other"})
g.add_edge("issue", "summarizor")
g.add_edge("rootcause", "summarizor")
g.add_edge("other", END)        
g.add_edge("summarizor", END)   

memory = MemorySaver()
orchestrator = g.compile(checkpointer = memory)