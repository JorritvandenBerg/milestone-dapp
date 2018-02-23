FROM python:3.5

RUN apt-get update && apt-get install -y libleveldb-dev

RUN pip3 install redis

RUN git clone https://github.com/CityOfZion/neo-python.git
WORKDIR /neo-python
RUN pip3 install -r requirements.txt
RUN pip3 install -e .

RUN rm -rf /neo-python/Chains/privatenet
RUN rm ./protocol.privnet.json
COPY ./protocol.privnet.json /neo-python/protocol.privnet.json

COPY src /src

WORKDIR /src/
CMD python3 run.py
