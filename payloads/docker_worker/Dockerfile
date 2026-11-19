FROM python:3.12-slim-bookworm
WORKDIR /app
COPY docker_worker/requirements.txt /tmp/web-lab-requirements.txt
RUN pip install --no-cache-dir -r /tmp/web-lab-requirements.txt
COPY domain/ /app/domain/
COPY prompts/ /app/prompts/
COPY web_assets/ /app/web_assets/
CMD ["python3", "-m", "mn_sdk.step_runtime"]
