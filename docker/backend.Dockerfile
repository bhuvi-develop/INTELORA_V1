# =============================================================================
# INTELORA Backend — FastAPI + Digital Twin Engine
#
# Python is pinned to 3.12: it is the newest release with stable prebuilt
# wheels for asyncpg and pydantic-core, which keeps image builds fast and
# reproducible without a compiler toolchain in the image.
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first so the layer caches independently of source changes.
COPY backend/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY backend/ /srv/

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 intelora \
    && chown -R intelora:intelora /srv
USER intelora

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
