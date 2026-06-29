FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID 1000 (before copying files)
RUN useradd -m -u 1000 bedrock_agentcore

# Copy requirements file and install dependencies as root (for pip cache access)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all agent code files with correct ownership
COPY --chown=bedrock_agentcore:bedrock_agentcore . .

# Switch to non-root user
USER bedrock_agentcore

# Expose port for AgentCore Runtime
EXPOSE 8080

# Add health check for /ping endpoint (AgentCore SDK provides this automatically)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

# Run with OpenTelemetry instrumentation for observability
CMD ["opentelemetry-instrument", "python", "main.py"]
