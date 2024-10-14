# Digital `Travel Assistant` 🤖 with LangGraph

This repository contains a modular and compact implementation of an end-to-end multi-agent architecture for a travel assistant chatbot, inspired by the [LangGraph's Travel Assistant project](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/). 
The original notebook has been transformed into a fully-fledged chatbot application.

      A multi-agent architecture featuring separate specialized agents for different tasks and an orchestrator to manage the workflow.

![Customer Support](https://langchain-ai.github.io/langgraph/tutorials/customer-support/img/part-4-diagram.png)

## How to Use


- set your environment variables

```dotenv
cp .env.example .env

# add to the file
OPEN_AI_KEY="add-your-key"
TAVILY_API_KEY="add-your-key"
```


- run the demo
```bash
docker compose up
```