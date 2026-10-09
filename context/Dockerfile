FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY skills ./skills
RUN pip install --no-cache-dir ".[server]"

ENV HOST=0.0.0.0
ENV PORT=8000
EXPOSE 8000

CMD ["aictx-mcp"]
