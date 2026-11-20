FROM nvcr.io/nvidia/isaac-sim:6.2.0@sha256:a025b65a7442d56806a1cc3f5eed081caf736c24b72d62dccf68ef66945d8690

USER root
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display
ENV VK_DRIVER_FILES=/etc/vulkan/icd.d/nvidia_icd.json
ENV ACCEPT_EULA=Y
ENV PRIVACY_CONSENT=N

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/bin/python3 -m venv /opt/mn-venv \
    && /opt/mn-venv/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3, 12)'

ENV PATH="/opt/mn-venv/bin:${PATH}"

COPY docker_worker/requirements.txt /tmp/web-lab-requirements.txt
RUN /opt/mn-venv/bin/python3 -m pip install --no-cache-dir --target /opt/web-lab-deps -r /tmp/web-lab-requirements.txt

WORKDIR /app
COPY domain/ /app/domain/
COPY isaac/ /app/isaac/
COPY web_assets/ /app/web_assets/

ENTRYPOINT []
HEALTHCHECK NONE
CMD ["/opt/mn-venv/bin/python3", "-m", "mn_sdk.step_runtime"]
