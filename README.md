# Milestone
Milestone is a decentralized platform for virtual collaboration. It allows to add conditional digital asset payments to the succesful execution of a project task.
The front-end is hosted on https://www.mstone.io and provides an interface to create milestones, but the smart contract can also be used directly. That requires attaching assets when invoking the 'milestone' operation.

This GIT repository contains the smart contract, middleware and a Python interface for application servers like Flask. The interface relies both on
RPC methods and Redis messages to the middleware. The smart contract operations are included in the Usage paragraph below.

This package also contains the tools for a private net deployement in a Docker environment.

## Table of Contents

- [Disclaimer](#disclaimer)
- [Installation](#installation)
- [Usage](#usage)
- [Maintainer](#maintainer)
- [License](#license)

## Disclaimer
This smart contract is for experimenal purposes and requires rigorous testing before deployment on the Main Net.

## Installation

### Dependencies

1. Install GIT
[GIT installation guide] (https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

2. Install Docker CE and docker-compose
[Docker CE installation guide] (https://docs.docker.com/engine/installation/)

3. To use Docker without sudo

``` bash
# Add your username to the Docker group
sudo usermod -aG docker $USER

# Logout and login again for this to take effect
logout
 ```

## Usage
To deploy the smart contract, it first needs to be set to the correct OWNER. In this example it is set to the corresponding owner of the wallet neo-privnet.wallet. The script can be compiled with pip neo-boa and deployed with the neo-python container.

Having Docker installed, you could do it like this:

``` bash
# Clone the git repository
git clone https://github.com/JorritvandenBerg/milestone-dapp.git

# Go to the milestone_dapp directory
cd milestone-dapp

# Build the Docker images
docker-compose build

# Run the containers (the middleware container will most likely fail but that is okay for now)
docker-compose up -d

# Attach to the neo-python container
docker attach milestone-dapp_neo_python_1

# Open the neo-privnet.wallet (password is coz)
open wallet /wallets/neo-privnet.wallet

# Rebuild the wallet
wallet rebuild

# Check if the wallet is synced (usually fast on private net)
wallet

# Import the contract (with storage enabled)
import contract /contracts/milestone.avm 0710 05 True

# Fill in the metadata form and optionally deploy with your wallet password after a succesful test invoke

# Wait a few minutes for deployment and grab the contract script hash with
contract search <entered author name>

# Go crazy with some test invokes
testinvoke <script_hash> fee []
testinvoke <script_hash> setFee [2]
testinvoke <script_hash> milestone ['milestone_key1', 'parent_agreement2', 'AXAmGd22VaF7w8c5wd5t43HJs9p9WwymMv', 'AVTENjYfJDhtYyNTtmqSxKPx5watyFRqz4', 'github', '1522540800', '1', 'AQ2CAEAmXzCm3yB4ZfwRAuNA6973S2Ehv3', '5', 'NEOGAS', '60']
testinvokle <script_hash> review ['milestone_key1', '60']
testinvoke <script_hash> deleteMilestone ['milestone_key1']
testinvoke <script_hash> refund ['milestone_key1', False]

# Dettach from the neo-python container (run "wallet close" if you intend to stop the container)
ctrl p + ctrl q

# Add the script hash to secrets.env (SCRIPT_HASH) and choose a token for REDIS_AUTH_TOKEN to secure your middleware

# Restart the middleware image
docker-compose restart middleware

 ```

Important: these Docker containers make use of named volumes (private_chain and contracts) to share data among each other and provide persistant storage.
To remove both the containers and volumes, you have to use "docker-compose down -v". This will delete all the data!

## Maintainers

[@JorritvandenBerg](mailto:jorrit_van_den_berg@hotmail.com)

## License

[License](LICENSE)
