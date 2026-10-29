FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Provide ANTHROPIC_API_KEY at runtime: docker run -e ANTHROPIC_API_KEY=... -p 8501:8501 equity-workspace
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
