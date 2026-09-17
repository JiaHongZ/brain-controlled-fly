FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 MUJOCO_GL=osmesa \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libosmesa6 libgl1 libegl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
RUN useradd --create-home --uid 10001 fly
COPY --chown=fly:fly . /app
USER fly
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/health/ready',timeout=3)" || exit 1
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8501", "--no-browser"]
