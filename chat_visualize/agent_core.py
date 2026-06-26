import os, requests, operator
from dotenv import load_dotenv
load_dotenv()
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import weaviate
from langchain_openai import AzureOpenAIEmbeddings
import os
import base64
import json

embedder = AzureOpenAIEmbeddings(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_deployment=os.environ["AZURE_EMBEDDING_DEPLOYMENT"],
    api_version="version",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

@tool
def similar_document(problem : str)->str:
    """RETURN THE MOST APPROPRIATE TOOLS ACCORDING TO THE USERS SPECIFIC PROBLEM."""
    vec = embedder.embed_query(problem)
    HOST = os.environ.get("WEAVIATE_HOST", "localhost")
    with weaviate.connect_to_local(host=HOST, port=8080) as client:
        coll = client.collections.get("Document")
        res = coll.query.near_vector(vec, limit=3)
        chunks = [f"[{o.properties['source']}]\n{o.properties['text'][:500]}"
                    for o in res.objects]
    return "\n\n---\n\n".join(chunks) if chunks else "İlgili döküman bulunamadı."


@tool
def issue_open(title: str, description: str = "", priority: str = "",
             assignee_name: str = "", assignee_email: str = "") -> str:
    """NEW ISSUE GENERATOR, ALL FIELDS ARE REQUIRED: title, description, priority, assignee_name."""
    payload = {
        "title": title,
        "description": description,
        "priority": priority,
        "assignee_name": assignee_name or None,
        "assignee_email": assignee_email or None,
    }
    API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
    r = requests.post(f"{API_URL}/issues", json=payload)
    if r.status_code != 200:
        return f"Issue açılamadı (HTTP {r.status_code}): {r.text}"
    return f"Issue açıldı: #{r.json()['id']} '{title}'"


class AgentState(TypedDict):
    messages : Annotated[list[AnyMessage], operator.add]

class Agent:
    def __init__(self, model, tools, system="", checkpointer=None):
        self.system = system
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: END})
        graph.add_edge("action", "llm")
        graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)   
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)
        
    def exists_action(self, state: AgentState):
        return len(state['messages'][-1].tool_calls) > 0

    def call_llm(self, state: AgentState):
        messages = state['messages']
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        return {'messages': [self.model.invoke(messages)]}

    def take_action(self, state: AgentState):
        results = []
        for t in state['messages'][-1].tool_calls:
            print(f"pending {t['name']} {t['args']}")
            if t['name'] not in self.tools:
                result = "not ok"
            else:
                result = self.tools[t['name']].invoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        return {'messages': results}

Prompt = "YOU ARE AN ISSUE ASSISTANT. WHEN A USER WANTS TO OPEN AN ISSUE USE ISSUE_OPEN."


ROOTCAUSE_PROMPT = (
    "You are analyzing a root cause (root reason). "
    "Get the user's problem and retrieve the relevant documentation using the similar_document tool., "   # ← düzeltildi
    "And explain the possible root cause and proposed solution based ONLY on these documents.. "
)




model = AzureChatOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_deployment=os.environ["AZURE_CHAT_DEPLOYMENT"],
    api_version=os.environ.get("AZURE_API_VERSION"),
    temperature=0,
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)
memory = MemorySaver()
abot = Agent(model, [issue_open], system=Prompt, checkpointer=memory)

rootcause_agent = Agent(model, [similar_document], system=ROOTCAUSE_PROMPT)


def fetch_data_from_image(image_list) -> dict:
    try:
        content = [{"type": "text", "text":
            "These images are from a complaint form. Extract these fields and return ONLY JSON: "
            '{"title":"", "description":"", "priority":"low|medium|high", '
            '"assignee_name":"", "assignee_email":""}. Leave the area you cant find blank.'}]
        for img in image_list:
            b64 = base64.b64encode(img).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        out = model.invoke([HumanMessage(content=content)])
        text = out.content.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print("VISION ERROR:", repr(e))     
        return {}