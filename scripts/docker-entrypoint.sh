#!/bin/bash

mkdir -p /tmp/storage
rm -rf /tmp/storage/*
rm -rf logs/gunicorn-error.log
export PYTHONPATH=.
# export SOCKET_PROTOCOL_USING_HEADER_KEY=OFF
python src/main.py
