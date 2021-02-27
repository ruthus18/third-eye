FROM python:3.9

ENV PATH=/root/.poetry/bin:$PATH POETRY_VIRTUALENVS_CREATE=0 PYTHONPATH=/app
RUN apt-get update \
  && rm -rf /var/lib/apt/lists/* \
  && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

COPY . .
ENTRYPOINT ["/app/entrypoint.sh", "python", "-m", "app"]
