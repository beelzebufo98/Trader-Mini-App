FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY seed.py ./seed.py

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
