from langchain_core.runnables import Runnable, RunnableConfig
from chatbot.state import State
from chatbot.tools.llm import LLM
from chatbot.agents.agents_utilities import CompleteOrEscalate


# a wrapper class
class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


# a function for compose a runnable to be passed into the wrapper Assistant
def create_runnable(safe_tools, sensitive_tools, prompt):
    tools = safe_tools + sensitive_tools
    runnable = prompt | LLM.bind_tools(tools + [CompleteOrEscalate])
    return runnable
