FROM python:3.13-slim
WORKDIR /app
COPY . /app
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_FRAME_ART=0.1.0 pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "frame_art.web:app", "--host", "0.0.0.0", "--port", "8000"]
