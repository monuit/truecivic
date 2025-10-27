FROM python:3.13-slim

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends build-essential gcc libpq5 libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
# ARG UID=10001
# RUN adduser \
#     --disabled-password \
#     --gecos "" \
#     --home "/nonexistent" \
#     --shell "/sbin/nologin" \
#     --no-create-home \
#     --uid "${UID}" \
#     appuser

# Package installation code copied from https://github.com/astral-sh/uv-docker-example/blob/main/Dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency manifests separately so uv can leverage Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra production

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN uv sync --frozen --no-dev --extra production

ENV PATH="/app/.venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=parliament.settings

# Prepare static asset directories (match STATIC_ROOT/COMPRESS_ROOT) and collect
# assets using the project virtualenv managed by uv.
RUN mkdir -p /app/staticfiles /app/frontend_bundles && \
    uv run python manage.py collectstatic --noinput && \
    uv run python manage.py compress --settings=parliament.offline_compress_settings --force

# RUN mkdir /staticfiles && chown appuser /staticfiles && mkdir /frontend_bundles && chown appuser /frontend_bundles

# USER appuser

# Copy example settings if no settings exist
COPY config-examples/settings.py.example parliament/settings_railway.py
RUN test -f parliament/settings.py || cp parliament/settings_railway.py parliament/settings.py || true

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py verify_embeddings && gunicorn parliament.wsgi:application -c gunicorn.conf.py"]