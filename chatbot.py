import uuid
from chatbot.graph import graph
from langchain_core.messages import ToolMessage
from pathlib import Path
from chatbot.tools.Data import DataPreparer


def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)


if __name__ == "__main__":

    # set up the data if not already downloaded (prepare_all will check if files exist already)
    Path("./database").mkdir(parents=True, exist_ok=True)
    _d = DataPreparer()
    _d.prepare_all()

    # set up some default questions (change as you like!)
    user_input = [
        "Hi there, what time is my flight?",
        "Am I allowed to update my flight to something sooner? I want to leave later today.",
        "Update my flight to sometime next week then",
        "The next available option is great",
        "what about lodging and transportation?",
        "Yeah i think i'd like an affordable hotel for my week-long stay (7 days). And I'll want to rent a car.",
        "OK could you place a reservation for your recommended hotel? It sounds nice.",
        "yes go ahead and book anything that's moderate expense and has availability.",
        "Now for a car, what are my options?",
        "Awesome let's just get the cheapest option. Go ahead and book for 7 days",
        "Cool so now what recommendations do you have on excursions?",
        "Are they available while I'm there?",
        "interesting - i like the museums, what options are there? ",
        "OK great pick one and book it for my second day there.",
    ]

    # create unique chat id (passenger_id to help retrieve client info)
    config = {
        "configurable": {
            "passenger_id": "3442 587242",
            "thread_id": str(uuid.uuid4()),
        }
    }
    # hold a set of responses
    _printed = set()

    # run the graph with user questions
    for question in user_input:
        events = graph.stream({"messages": ("user", question)}, config, stream_mode="values")

        this_event = None
        for event in events:
            this_event = event
            _print_event(this_event, _printed)
        snapshot = graph.get_state(config)

        while snapshot.next:
            # We have an interrupt! The agent is trying to use a tool, and the user can approve or deny it
            # Note: This code is all outside of your graph. Typically, you would stream the output to a UI.
            # Then, you would have the frontend trigger a new run via an API call when the user has provided input.
            user_input = input("Do you approve of the above actions? Type 'y' to continue OR 'detailed instructions': ")
            if user_input.strip() == "y":
                # Just continue
                result = graph.invoke(None, config)
            else:
                # Satisfy the tool invocation by providing instructions on the requested changes / change of mind
                result = graph.invoke(
                    {
                        "messages": [
                            ToolMessage(
                                tool_call_id=this_event["messages"][-1].tool_calls[0]["id"],
                                content=f"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input.",
                            )
                        ]
                    },
                    config,
                )
            snapshot = graph.get_state(config)
