# AI-SHM-Web-services

A simple practice for deploying high-performance AI web services.

## IF run with Docker
* Create file .env based .env.example

* Create logs dir:
```bash
mkdir -p ./logs && chmod 777 ./logs
```

* RUN:
```bash
docker compose up -d
```

## ELSE run with Local

* Create file .env.local based .env.local.example
* Create conda envirioment based python 3.12 and requirements.txt

* Create logs dir:

```bash
mkdir -p ./local_logs
```

* RUN:
```bash
source <CONDA ENV>
bash scripts/local-entrypoint.sh
```