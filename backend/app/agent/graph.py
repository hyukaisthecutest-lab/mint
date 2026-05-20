from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session
from app.core.config import settings
from app.agent.tools import make_tools
from app.agent import guardrail
from app.agent.observer import AgentObserver
from app.core.telemetry import tracer, agent_blocked, agent_duration
from app.core.metrics_store import store

_SYSTEM = """You are a personal finance assistant with access to the user's real transaction data.
Always call the appropriate tool to get real data before answering.
Be specific, use actual numbers from the data, and keep responses conversational.
When suggesting cost reductions, base advice on the user's actual spending patterns.
Format all amounts as USD currency."""

_BLOCKED = "I can only help with questions about your personal finances, spending, and budget. Please ask me something related to your accounts or transactions."


def create_graph(user_id: str, db: Session, observer: AgentObserver | None = None):
    obs = observer or AgentObserver()
    tools = make_tools(user_id, db)
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        callbacks=[obs],
    ).bind_tools(tools)
    tool_node = ToolNode(tools, handle_tool_errors=True)

    def guardrail_node(state: MessagesState):
        import time
        t0 = time.perf_counter()
        with tracer.start_as_current_span("guardrail") as span:
            last: BaseMessage = state["messages"][-1]
            if isinstance(last, HumanMessage):
                passed = guardrail.is_finance_question(last.content)
                span.set_attribute("guardrail.passed", passed)
                agent_duration.labels(step="guardrail").observe(time.perf_counter() - t0)
                if not passed:
                    agent_blocked.inc()
                    store.record_blocked()
                    span.set_attribute("guardrail.blocked_message", last.content[:100])
                    return {"messages": [AIMessage(content=_BLOCKED, additional_kwargs={"blocked": True})]}
        return state

    def agent_node(state: MessagesState):
        import time
        t0 = time.perf_counter()
        with tracer.start_as_current_span("agent.think"):
            messages = [{"role": "system", "content": _SYSTEM}] + state["messages"]
            result = model.invoke(messages, config={"callbacks": [obs]})
            agent_duration.labels(step="agent").observe(time.perf_counter() - t0)
        return {"messages": [result]}

    def route_guardrail(state: MessagesState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.additional_kwargs.get("blocked"):
            return END
        return "agent"

    def route_agent(state: MessagesState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "guardrail")
    graph.add_conditional_edges("guardrail", route_guardrail, {"agent": "agent", END: END})
    graph.add_conditional_edges("agent", route_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()
