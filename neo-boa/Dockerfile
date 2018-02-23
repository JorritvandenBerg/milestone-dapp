FROM ubuntu:16.04

RUN apt-get update && apt-get -y install python3-dev python3-pip git

RUN pip3 install neo-boa==0.2.1

COPY compiler.py /compiler.py

CMD python3 compiler.py
