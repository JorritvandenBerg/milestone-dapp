FROM ubuntu:16.04

RUN apt-get update && apt-get -y install git python3-dev python3-pip libleveldb-dev libssl-dev screen

RUN git clone https://github.com/CityOfZion/neo-python.git

WORKDIR /neo-python

RUN git checkout development
RUN pip3 install -r requirements.txt

COPY ./neo-privnet.wallet /neo-python/wallets/neo-privnet.wallet
RUN sed -i 's/127.0.0.1/private_net/g' ./protocol.privnet.json

CMD rm -rf /neo-python/Chains/privnet; screen python3 prompt.py -p

