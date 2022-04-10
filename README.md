# VEIL node stratum proxy

This proxy written in python implements a simple stratum protocol which most of the mining software out there should understand (tested with [T-Rex](https://trex-miner.com/) miner), in order to be able to solo mine [VEIL](https://veil-project.com/) directly using a full local node and the mining software of your choice, without the need to use a mining pool or the only miner which currently supports mining directly to a node (TT-Miner).

## Setup

1. **Setup your VEIL full node** as described in https://veil-project.com/blog/2020-mineafterhardfork/.

   An example working `veil.conf` file is the following:
   ```
   rpcuser=veil
   rpcpassword=veil
   rpcbind=127.0.0.1
   rpcallowip=127.0.0.1
   rpcport=5556
   server=1
   listen=1
   mine=progpow
   miningaddress=<your-mining-address>
   ```
   **NOTE**: Replace `rpcuser`, `rpcpassword` and `<your-mining-address>` accordingly.
   `<your-mining-address>` must be a basecoin address which you can generate in the desktop wallet under `Settings > Advanced Options > Console > getnewbasecoinaddress`.

2. **Setup the proxy**:

   Install python dependencies (`python 3` required):
   ```bash
   pip install -r requirements.txt
   ```
   Start the proxy:
   ```bash
   # Replace veil:veil by your rpcuser:rpcpassword from veil.conf
   python3 veilproxy.py -p 5555 -n http://veil:veil@127.0.0.1:5556
   ```

3. **Start your miner!**

   Example for T-Rex miner (username and password for the proxy can be anything):
   ```bash
   ./t-rex --validate-shares -a progpow-veil --coin veil -o stratum+tcp://127.0.0.1:5555 -u x -p x
   ```

## Donations

Donations are on a voluntary basis and of course always much appreciated! Thanks!

**VEIL**: `sv1qqpjsrc60t60jhaywj5krmwla52ska70twc7wun6qnee65guxhvtxegpqwhuxypra4jn3pq86s24ryltcw6g2ss4573hyqac9u4g23m9mvxpyqqqwny49k`
