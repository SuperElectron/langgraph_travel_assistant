from typing import Literal

from langchain_core.runnables import Runnable
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableLambda

from chatbot.tools.FlightService import FlightService
from chatbot.tools.CarService import CarService
from chatbot.tools.HotelService import HotelService
from chatbot.tools.ExcursionService import ExcursionService

flight_service = FlightService()
car_service = CarService()
hotel_service = HotelService()
excursion_service = ExcursionService()


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks([RunnableLambda(handle_tool_error)], exception_key="error")


from chatbot.state import State
from chatbot.agents.agents_utilities import (
    create_entry_node,
    CompleteOrEscalate,
)
from chatbot.agents.assistant_wrapper import Assistant
from chatbot.agents.specialized_assistants import (
    flight_booking_runnable,
    excursion_runnable,
    car_rental_runnable,
    hotel_booking_runnable,
)
from chatbot.agents.primary_assistant import (
    primary_assistant_runnable,
    primary_assistant_tools,
    ToHotelBookingAssistant,
    ToBookCarRental,
    ToBookExcursion,
    ToFlightBookingAssistant,
)

# Let's compose the graph
builder = StateGraph(State)


# Fetching the User info
# function for fetching user info: tool's action function
def user_info(state: State):
    fi = FlightService()
    u_info = fi.fetch_user_flight_information()
    return {"user_info": u_info}


builder.add_node("fetch_user_info", RunnableLambda(user_info))
builder.add_edge(START, "fetch_user_info")


# specialized workflow factory functions: graph_add_specialized_workflows & route_update_workflow
def graph_add_specialized_workflows(
        graph_builder: StateGraph,
        dialog_state: str,
        assistant_name: str,
        assistant_runnable: Runnable,
        safe_tools: list,
        sensitive_tools: list,
):
    # assistant entry node
    graph_builder.add_node(
        node=f"enter_{dialog_state}",
        action=create_entry_node(assistant_name=assistant_name, new_dialog_state=dialog_state),
    )
    # assistant node
    graph_builder.add_node(node=dialog_state, action=Assistant(assistant_runnable))

    # add edge: entry_node --> assistant_node
    graph_builder.add_edge(start_key=f"enter_{dialog_state}", end_key=dialog_state)

    # add safe tools node
    graph_builder.add_node(
        node=f"{dialog_state}_safe_tools",
        action=create_tool_node_with_fallback(safe_tools),
    )
    # add sensitive tools node
    graph_builder.add_node(
        node=f"{dialog_state}_sensitive_tools",
        action=create_tool_node_with_fallback(sensitive_tools),
    )

    # add edge: safe_tools_node --> assistant_node
    graph_builder.add_edge(f"{dialog_state}_safe_tools", dialog_state)

    # add edge: sensitive_tools_node --> assistant_node
    graph_builder.add_edge(f"{dialog_state}_sensitive_tools", dialog_state)

    # add conditional edge: assistant_node --> route_update_flight
    def route_update_workflow(state: State) -> str:
        route = tools_condition(state)
        if route == END:
            return END

        tool_calls = state["messages"][-1].tool_calls
        did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
        if did_cancel:
            return "leave_skill"

        # decide if we should return safe_tools or sensitive_tools
        safe_toolnames = [t.__name__ for t in safe_tools]
        if all(tc["name"] in safe_toolnames for tc in tool_calls):
            return f"{dialog_state}_safe_tools"

        return f"{dialog_state}_sensitive_tools"

    builder.add_conditional_edges(
        dialog_state,
        route_update_workflow,
    )
    return graph_builder


# flight assistant
builder = graph_add_specialized_workflows(
    graph_builder=builder,
    dialog_state="update_flight",
    assistant_name="Flight Updates & Booking Assistant",
    assistant_runnable=flight_booking_runnable,
    safe_tools=flight_service.get_safe_tools(),
    sensitive_tools=flight_service.get_sensitive_tools(),
)

# car rental assistant
builder = graph_add_specialized_workflows(
    graph_builder=builder,
    dialog_state="book_car_rental",
    assistant_name="Car Rental Assistant",
    assistant_runnable=car_rental_runnable,
    safe_tools=car_service.get_safe_tools(),
    sensitive_tools=car_service.get_sensitive_tools(),
)

# hotel booking assistant
builder = graph_add_specialized_workflows(
    graph_builder=builder,
    dialog_state="book_hotel",
    assistant_name="Hotel Booking Assistant",
    assistant_runnable=hotel_booking_runnable,
    safe_tools=hotel_service.get_safe_tools(),
    sensitive_tools=hotel_service.get_sensitive_tools(),
)

# excursions assistant
builder = graph_add_specialized_workflows(
    graph_builder=builder,
    dialog_state="book_excursion",
    assistant_name="Trip Recommendation Assistant",
    assistant_runnable=excursion_runnable,
    safe_tools=excursion_service.get_safe_tools(),
    sensitive_tools=excursion_service.get_sensitive_tools(),
)


# This node will be shared for exiting all specialized assistants
def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
    }


builder.add_node("leave_skill", pop_dialog_state)
builder.add_edge("leave_skill", "primary_assistant")

# 3. Add Primary Assistant
builder.add_node("primary_assistant", Assistant(primary_assistant_runnable))
builder.add_node(
    "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)
)


def route_primary_assistant(
        state: State,
) -> Literal[
    "primary_assistant_tools",
    "enter_update_flight",
    "enter_book_hotel",
    "enter_book_excursion",
    "__end__",
]:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
            return "enter_update_flight"
        elif tool_calls[0]["name"] == ToBookCarRental.__name__:
            return "enter_book_car_rental"
        elif tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"
        elif tool_calls[0]["name"] == ToBookExcursion.__name__:
            return "enter_book_excursion"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


# The assistant can route to one of the delegated assistants,
# directly use a tool, or directly respond to the user
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    {
        "enter_update_flight": "enter_update_flight",
        "enter_book_car_rental": "enter_book_car_rental",
        "enter_book_hotel": "enter_book_hotel",
        "enter_book_excursion": "enter_book_excursion",
        "primary_assistant_tools": "primary_assistant_tools",
        END: END,
    },
)
builder.add_edge("primary_assistant_tools", "primary_assistant")


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
        state: State,
) -> Literal[
    "primary_assistant",
    "update_flight",
    "book_car_rental",
    "book_hotel",
    "book_excursion",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


builder.add_conditional_edges("fetch_user_info", route_to_workflow)

# Compile graph
memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory,
    # Let the user approve or deny the use of sensitive tools
    interrupt_before=[
        "update_flight_sensitive_tools",
        "book_car_rental_sensitive_tools",  # car_service.get_sensitive_tools
        "book_hotel_sensitive_tools",
        "book_excursion_sensitive_tools",
    ],
)
