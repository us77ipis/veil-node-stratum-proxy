# VEIL node stratum proxy

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/us77ipis/veil-node-stratum-proxy?display_name=tag&cacheSeconds=3600)](https://github.com/us77ipis/veil-node-stratum-proxy/releases)
[![GitHub Release Date](https://img.shields.io/github/release-date/us77ipis/veil-node-stratum-proxy?cacheSeconds=3600)](https://github.com/us77ipis/veil-node-stratum-proxy/releases)

This proxy written in python implements a simple stratum protocol which most of the mining software out there should understand (tested with [T-Rex](https://trex-miner.com/), [WildRig](https://github.com/andru-kun/wildrig-multi) and [xmrig](https://xmrig.com/) miner), in order to be able to solo mine [VEIL](https://veil-project.com/) directly using a full local node and the mining software of your choice, without the need to use a mining pool or the only miner which currently supports mining directly to a node (TT-Miner).

The proxy can be used to mine both ProgPoW VEIL and RandomX VEIL.

## Setup

1. **Setup your VEIL full node** as described in https://veil-project.com/blog/2020-mineafterhardfork/.

   **NOTE**: Make sure you are running **wallet version [v1.4.0.0](https://github.com/Veil-Project/veil/releases) or higher**.

   An example working `veil.conf` file is the following:
   ```
   rpcuser=veil
   rpcpassword=veil
   rpcbind=127.0.0.1
   rpcallowip=127.0.0.1
   rpcport=5556
   server=1
   listen=1
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
   # You can use option -a to change the listen address
   # You can use option -j to show jobs in the log
   python3 veilproxy.py -p 5555 -n http://veil:veil@127.0.0.1:5556 -j
   ```

3. **Start your miner!** Note that username and password for the proxy can be anything.

   Example for **T-Rex ProgPoW** miner (**T-Rex 0.26.6 or higher required**):
   ```bash
   # For Linux
   ./t-rex --validate-shares -a progpow-veil --coin veil -o stratum+tcp://127.0.0.1:5555 -u x -p x
   # For Windows
   t-rex.exe --validate-shares -a progpow-veil --coin veil -o stratum+tcp://127.0.0.1:5555 -u x -p x
   ```

   Example for **WildRig ProgPoW** miner (**WildRig 0.32.1 or higher required**):
   ```bash
   # For Linux
   ./wildrig --print-full -a progpow-veil -o 127.0.0.1:5555 -u x -p x
   # For Windows
   wildrig.exe --print-full -a progpow-veil -o 127.0.0.1:5555 -u x -p x
   ```

   Example for **xmrig RandomX** miner:
   ```bash
   # For Linux
   ./xmrig -o 127.0.0.1:5555 -u x -p x
   # For Windows
   xmrig.exe -o 127.0.0.1:5555 -u x -p x
   ```
   **NOTE**: xmrig with VEIL support is not yet released. Until then, you have to build it from source. To do this, follow the [**official xmrig build guide**](https://xmrig.com/docs/miner/build), but use the repository https://github.com/us77ipis/xmrig-veil instead of https://github.com/xmrig/xmrig. This note will be updated once the changes are merged into the official xmrig repository.


## Donations

Donations are on a voluntary basis and of course always much appreciated! Thanks!

**VEIL**: `sv1qqpjsrc60t60jhaywj5krmwla52ska70twc7wun6qnee65guxhvtxegpqwhuxypra4jn3pq86s24ryltcw6g2ss4573hyqac9u4g23m9mvxpyqqqwny49k`
