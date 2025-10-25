FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN mkdir /app
WORKDIR /app

ADD pyproject.toml uv.lock /app/
RUN uv sync

ADD . /app/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "stv_demo_site.main:app", "--host", "0.0.0.0", "--port", "8000"]
