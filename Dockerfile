FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy the requirements.txt file into the container at /app
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# default run command for container
CMD ["python3", "chatbot.py"]
