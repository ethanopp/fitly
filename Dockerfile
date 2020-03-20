FROM tiangolo/meinheld-gunicorn:python3.7
LABEL maintainer="maintainer"

RUN git clone https://github.com/ethanopp/fitly.git

RUN pip install -U pip && pip install -r ./fitly/requirements.txt

RUN mv ./fitly/* /app/ && rm -rf ./fitly

ENV NGINX_WORKER_PROCESSES auto