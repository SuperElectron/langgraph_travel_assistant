from typing import Literal, Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages, AnyMessage


def update_dialogue_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state"""

    if right is None:  # do not touch of right is None
        return left
    if right == "pop":  # remove the last element of the str list [left]
        return left[:-1]

    return left + [right]  # if right is not None and is not pop, extend the list


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                "update_flight",  # dialog_state = is a list: represents the current state of the dalogue
                "book_car_rental",  # The update_dialogue_stack function manages how this list is updated
                "book_hotel",
                "book_excursion",
            ]
        ],
        update_dialogue_stack,
    ]


"""
Example:
Imagine a user interacting with the chatbot:

The initial dialog_state might be ["assistant"].
The user asks to update their flight, so "update_flight" is added to the dialog_state:
The stack becomes ["assistant", "update_flight"].
The user then decides to book a hotel, so "book_hotel" is added:
The stack becomes ["assistant", "update_flight", "book_hotel"].
If the user completes the hotel booking, the system might pop "book_hotel" off the stack:
The stack returns to ["assistant", "update_flight"].
"""
