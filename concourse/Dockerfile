#========================================================================================
# This Dockerfile creates a container image which contains python 3.8 and google chrome,
# as well as the application source and bundled dependencies.
#
# This is needed for running the feature tests in a container environment like concourse.
#========================================================================================
FROM from python:3.8-alpine

RUN apt-get update --fix-missing && apt-get -y upgrade \
    && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends \
      ./google-chrome-stable_current_amd64.deb \
      default-jre \
    && rm ./google-chrome-stable_current_amd64.deb

ENV CHROME_NO_SANDBOX=true

RUN apk add --no-cache openssl-dev libffi-dev build-base

COPY requirements.txt /application/

WORKDIR /application/

RUN pip install -r requirements.txt

COPY . /application/

ENTRYPOINT ["/bin/bash"]
