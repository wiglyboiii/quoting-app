# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libpango-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    --no-install-recommends

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Make port 10000 available to the world outside this container
# Render will use this port by default for web services
EXPOSE 10000

# Define environment variable for Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]