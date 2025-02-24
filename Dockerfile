FROM python:3.9-slim

WORKDIR /app

# Install dependencies from the requirements file located in src/
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire src folder content into /app
COPY src/ .

# Ensure the database directory exists for volume mounting
RUN mkdir -p /app/database

# Run the bot (make sure main.py is your entrypoint)
CMD ["python", "main.py"]
