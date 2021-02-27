FROM python:3.9

RUN apt-get update \
  && rm -rf /var/lib/apt/lists/* \
  && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

ENV PATH /root/.poetry/bin:$PATH
ENV POETRY_VIRTUALENVS_CREATE=0 PYTHONPATH=/app
WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY . .
ENTRYPOINT ["/app/entrypoint.sh", "python", "-m", "app"]
