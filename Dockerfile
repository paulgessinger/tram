FROM python:3.13-slim

ENV USER=tram
RUN adduser --gecos "" --disabled-password $USER

RUN pip install --no-cache-dir uv

RUN mkdir /app
WORKDIR /app

COPY . /app

ENV PATH=/home/$USER/.local/bin:$PATH

RUN uv venv \
  && uv pip install -r requirements.txt \
  && uv pip install waitress
ENV PATH="/app/.venv/bin:$PATH"

USER $USER
CMD ["waitress-serve", "--port", "5000", "web:app"]
