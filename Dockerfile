FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Add src to Python path so "bot" package is discoverable
ENV PYTHONPATH=/app/src

# Create non-root user for security
RUN adduser --disabled-password --no-create-home appuser
USER appuser

# Run migrations and start bot
CMD alembic upgrade head && python -m bot.main
