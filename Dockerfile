FROM python:3.13-slim

ENV USER=tram
RUN adduser --gecos "" --disabled-password $USER

RUN pip install --no-cache-dir uv

RUN mkdir /app

COPY . /app

ENV PATH=/home/$USER/.local/bin:$PATH
ENV TZ="Europe/Zurich"

RUN uv venv \
  && uv pip install -r /app/requirements.txt \
  && uv pip install waitress
ENV PATH="/.venv/bin:$PATH"
WORKDIR /app

USER $USER
CMD ["waitress-serve", "--port", "5000", "web:app"]
