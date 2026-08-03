FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df AS builder

RUN apk add --no-cache build-base libffi-dev
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/configurator-venv \
    && /opt/configurator-venv/bin/pip install --no-cache-dir --upgrade pip==25.1.1 \
    && /opt/configurator-venv/bin/pip install --no-cache-dir .

FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df

RUN apk add --no-cache \
      alsa-utils \
      bash \
      docker-cli \
      docker-cli-compose \
      iputils \
      libstdc++ \
      tini
COPY --from=builder /opt/configurator-venv /opt/configurator-venv
ENV PATH="/opt/configurator-venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HARU_CONFIGURATOR_SCHEMA_VERSION=4 \
    HOME=/tmp/haru-home
USER 65532:65532
ENTRYPOINT ["/sbin/tini", "--", "haru-local"]
CMD ["setup"]
