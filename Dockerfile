FROM python:3.9-slim
LABEL maintainer="James Turk <dev@jamesturk.net>"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONIOENCODING='utf-8'
ENV LANG='C.UTF-8'

RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      ca-certificates \
      curl \
      wget \
      unzip \
      mdbtools \
      libpq5 \
      libgdal32 \
      build-essential \
      git \
      libssl-dev \
      libffi-dev \
      freetds-dev \
      libxml2-dev \
      libxslt-dev \
      libyaml-dev \
      poppler-utils \
      libpq-dev \
      libgdal-dev \
      libgeos-dev \
      gnupg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends gh
RUN pip --no-cache-dir --disable-pip-version-check install wheel \
    && pip --no-cache-dir --disable-pip-version-check install crcmod poetry

ADD poetry.lock /opt/openstates/openstates/
ADD pyproject.toml /opt/openstates/openstates/
WORKDIR /opt/openstates/openstates/
ENV PYTHONPATH=./scrapers

RUN poetry install --no-root

ADD . /opt/openstates/openstates/

ARG CRONOS_ENDPOINT
ENV CRONOS_ENDPOINT=${CRONOS_ENDPOINT}
ARG CACHE_BUCKET
ENV CACHE_BUCKET=${CACHE_BUCKET}

ARG ELASTIC_CLOUD_ID
ENV ELASTIC_CLOUD_ID=${ELASTIC_CLOUD_ID}

ARG ELASTIC_BASIC_AUTH_USER
ENV ELASTIC_BASIC_AUTH_USER=${ELASTIC_BASIC_AUTH_USER}

ARG ELASTIC_BASIC_AUTH_PASS
ENV ELASTIC_BASIC_AUTH_PASS=${ELASTIC_BASIC_AUTH_PASS}

ENV ARCHIVE_CACHE_TO_S3=true

RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
  && unzip -q awscliv2.zip \
  && ./aws/install \
  && rm -rf aws awscliv2.zip
# the last step cleans out temporarily downloaded artifacts for poetry, shrinking our build
RUN poetry install --no-root \
    && rm -r /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/ \
    && apt-get remove -y -qq \
      build-essential \
      libpq-dev \
    && apt-get autoremove -y -qq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV OPENSSL_CONF=/opt/openstates/openstates/openssl.cnf

# Entrypoint enables proper support of Google Application Credentials as env variable
COPY docker_entrypoint.sh /opt/openstates/entrypoint.sh
ENTRYPOINT ["/bin/bash", "/opt/openstates/entrypoint.sh"]
