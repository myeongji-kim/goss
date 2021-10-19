FROM  python:3.8-slim-buster

USER root
RUN apt-get install libffi6

RUN pip install cffi \
	&& pip install paramiko \
	&& pip install requests \
	&& pip install pytest-parallel \
	&& pip install pytest-html \
	&& pip install pytest
