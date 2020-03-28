FROM tiangolo/meinheld-gunicorn:python3.7
LABEL maintainer="ethanopp"

COPY . .

RUN pip install -U pip && pip install -r ./requirements.txt

ENV NGINX_WORKER_PROCESSES auto
