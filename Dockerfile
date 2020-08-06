from python:3.8-alpine

RUN apk add --no-cache openssl-dev libffi-dev build-base
RUN mkdir app
WORKDIR app
COPY . .
RUN pip install -r requirements.txt
ENV FLASK_ENV=production
ENV FLASK_APP=run.py
CMD flask run --host 0.0.0.0 --port 5000
