import argparse
import asyncio
import aiohttp
import json
import random
import secrets
import string
import logging
import coloredlogs
from hashlib import sha256


def prune0x(s):
    return s[2:] if s.startswith('0x') else s

def reverseEndianess(s):
    b = bytearray.fromhex(s)
    b.reverse()
    return b.hex()


def formatDiff(target):
    diff = 0xffffffffffffffff / int(target[:16], 16)
    UNITS = [(1000000000000, 'T'), (1000000000, 'G'), (1000000, 'M'), (1000, 'K')]
    for l, u in UNITS:
        if diff > l:
            return '{:.2f}{}'.format(diff / l, u)


class NodeConnection:
    def __init__(self, url, logger):
        self.url = url
        self.logger = logger
        self.lastJob = None
        self.session = None
        self.subscribers = []
        self.submissionCounter = 0
        self.successfulSubmissionCounter = 0

    @property
    def tag(self):
        raise NotImplementedError("Not implemented yet")

    def getblocktemplateJSON(self):
        raise NotImplementedError("Not implemented yet")

    def submitJSON(self):
        raise NotImplementedError("Not implemented yet")

    def setJobId(self, job):
        raise NotImplementedError("Not implemented yet")

    async def run(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2000)) as self.session:
            while True:
                try:
                    data = self.getblocktemplateJSON()

                    if self.lastJob:
                        data['params'][0]['longpollid'] = self.lastJob['longpollid']

                    async with self.session.post(self.url, json=data) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data['error']:
                                self.logger.error('RPC error (%d): %s',
                                                  data['error']['code'],
                                                  data['error']['message'])
                            else:
                                job = data['result']
                                if not self.lastJob or job['longpollid'] != self.lastJob['longpollid']:
                                    self.setJobId(job)
                                    lastJob = self.lastJob
                                    self.lastJob = job
                                    if not lastJob or lastJob['job_id'] != job['job_id']:
                                        if SHOW_JOBS:
                                            self.logger.info('New %s job diff \x1b[1m%s\x1b[0m height \x1b[1m%d\x1b[0m',
                                                            self.tag, formatDiff(job['target']), job['height'])
                                        for s in self.subscribers:
                                            try:
                                                s.onNewJob(job)
                                            except asyncio.CancelledError:
                                                raise
                                            except Exception:
                                                pass
                        elif resp.status == 401:
                            self.logger.critical('RPC error: Unauthorized. Wrong username/password?')
                            await asyncio.sleep(10)
                        else:
                            self.logger.critical('Unknown RPC error: status code ' + str(resp.status))
                            await asyncio.sleep(10)
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    self.logger.error('RPC error: %s', str(e))
                    await asyncio.sleep(1)

    @property
    def countersStr(self):
        failedSubmissionCount = self.submissionCounter - self.successfulSubmissionCounter
        ff = '\x1b[31m{}\x1b[0m' if failedSubmissionCount > 0 else '{}'
        return ('(\x1b[32m{}\x1b[0m/' + ff + ')').format(
            self.successfulSubmissionCounter, failedSubmissionCount)

    async def submit(self, *args, **kwargs):
        self.submissionCounter += 1
        try:
            data = self.submitJSON(*args, **kwargs)

            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug('Submitting block to node %s', json.dumps(data))

            async with self.session.post(self.url, json=data) as resp:
                res = await resp.json()
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug('Block submission response %s', json.dumps(res))
                if 'result' in res:
                    if res['result'] is True:
                        self.successfulSubmissionCounter += 1
                        self.logger.info('\x1b[32mBlock submission succeeded\x1b[0m %s',
                                         self.countersStr)
                        return True
                    elif res['result']:
                        self.logger.error('Block submission failed: %s', str(res['result']))
                        return { 'code': 26, 'message': res['result'] }
                if 'error' in res:
                    self.logger.error('Block submission failed (%d): %s',
                                  res['error']['code'], res['error']['message'])
                    return res['error']
                self.logger.error('Unknown block submission error')
                return { 'code': 25, 'message': 'Unknown error' }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error('Block submission RPC error: %s', str(e))
            return { 'code': 24, 'message': str(e) }


class PPNodeConnection(NodeConnection):
    def __init__(self, url, logger):
        super().__init__(url, logger)

    @property
    def tag(self):
        return '\x1b[0;36mprogpow\x1b[0m'

    def getblocktemplateJSON(self):
        return {
            'jsonrpc': '1.0',
            'method': 'getblocktemplate',
            'params': [{ "algo": "progpow" }],
        }

    def submitJSON(self, header_hash, mix_hash, nonce):
        return {
            'jsonrpc': '1.0',
            'method': 'pprpcsb',
            'params': [header_hash, mix_hash, nonce],
        }

    def setJobId(self, job):
        if 'pprpcheader' in job and 'pprpcnextepoch' not in job:
            self.logger.critical('Update your VEIL wallet to version 1.4.0.0 or higher')
            exit(1)
        elif 'pprpcheader' not in job:
            self.logger.critical('Your VEIL wallet is either misconfigured or not up-to-date. Did you set a miningaddress in the veil.conf?')
            exit(1)
        job['job_id'] = job['pprpcheader']


class RXNodeConnection(NodeConnection):
    def __init__(self, url, logger):
        super().__init__(url, logger)

    @property
    def tag(self):
        return '\x1b[0;33mrandomx\x1b[0m'

    def getblocktemplateJSON(self):
        return {
            'jsonrpc': '1.0',
            'method': 'getblocktemplate',
            'params': [{ "algo": "randomx" }],
        }

    def submitJSON(self, header, rx_hash, nonce):
        return {
            'jsonrpc': '1.0',
            'method': 'rxrpcsb',
            'params': [header, rx_hash, nonce],
        }

    def setJobId(self, job):
        job['job_id'] = sha256(job['rxrpcheader'].encode()).hexdigest()


class ServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.client_addr   = transport.get_extra_info('peername')
        self.transport     = transport
        self.loginId       = None
        self.node          = None
        logging.info('Connection with client %s:%d established', *self.client_addr)

    def connection_lost(self, exception):
        logging.info('Connection with client %s:%d closed.', *self.client_addr)

        if self.node:
            self.node.subscribers.remove(self)

    def send(self, data):
        data['jsonrpc'] = '2.0'
        self.transport.write(json.dumps(data).encode() + b'\n')

    async def submitPP(self, id, header_hash, mix_hash, nonce):
        res = await self.node.submit(header_hash, mix_hash, nonce)
        if res == True:
            self.send({ 'id': id, 'result': True })
        else:
            self.send({ 'id': id, 'result': False, 'error': res })

    async def submitRX(self, id, header, rx_hash, nonce):
        res = await self.node.submit(header, rx_hash, nonce)
        if res == True:
            self.send({ 'id': id, 'result': { 'status': 'OK' } })
        else:
            self.send({ 'id': id, 'result': None, 'error': res })

    def data_received(self, data):
        try:
            d = json.loads(data)
            id = d['id'] if 'id' in d else None
            if 'method' in d and 'params' in d:
                if self.node == PPNODE and d['method'] == 'mining.submit':
                    if len(d['params']) == 5:
                        jobId = d['params'][1]
                        nonce = prune0x(d['params'][2])
                        header_hash = prune0x(d['params'][3])
                        mix_hash = prune0x(d['params'][4])
                        if self.node.lastJob and self.node.lastJob['job_id'] == jobId:
                            asyncio.ensure_future(self.submitPP(id, header_hash, mix_hash, nonce))
                        else:
                            self.send({
                                'id': id,
                                'error': {
                                    'code': 23,
                                    'message': 'Stale share.'
                                }
                            })
                    else:
                        self.send({
                            'id': id,
                            'error': {
                                'code': 22,
                                'message': 'Bad request: expected 5 parameters but got' + str(len(d['params'])) + '.'
                            }
                        })
                elif self.node == RXNODE and d['method'] == 'submit':
                    if all(k in d['params'] for k in ['job_id', 'nonce', 'result']):
                        jobId = d['params']['job_id']
                        nonce = reverseEndianess(d['params']['nonce'])
                        rx_hash = d['params']['result']
                        if self.node.lastJob and self.node.lastJob['job_id'] == jobId:
                            asyncio.ensure_future(self.submitRX(id, self.node.lastJob['rxrpcheader'], rx_hash, nonce))
                        else:
                            self.send({
                                'id': id,
                                'error': {
                                    'code': 23,
                                    'message': 'Stale share.'
                                }
                            })
                    else:
                        self.send({
                            'id': id,
                            'error': {
                                'code': 22,
                                'message': 'Bad request: expected "job_id", "nonce" and "result" parameters.'
                            }
                        })
                elif self.node != RXNODE and d['method'] == 'mining.subscribe':
                    if not self.node:
                        self.node = PPNODE
                        self.node.subscribers.append(self)

                        ids = [''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(13)),
                               secrets.token_hex(2)]
                        self.send({ 'id': id, 'result': ids, 'error': None })
                        self.onNewJob()
                    else:
                        self.send({
                            'id': id,
                            'error': { 'code': 21, 'message': 'Already subscribed.' }
                        })
                elif self.node == PPNODE and d['method'] == 'mining.authorize' or d['method'] == 'mining.extranonce.subscribe':
                    self.send({ 'id': id, 'result': True, 'error': None })
                elif self.node != PPNODE and d['method'] == 'login':
                    if not self.node:
                        self.node = RXNODE
                        self.node.subscribers.append(self)
                        self.onNewJob(loginId=id)
                    else:
                        self.send({
                            'id': id,
                            'error': { 'code': 21, 'message': 'Already subscribed.' }
                        })
                else:
                    self.send({
                        'id': id,
                        'error': {
                            'code': 20,
                            'message': 'Unsupported request ' + str(d['method'])
                        }
                    })
        except json.JSONDecodeError:
            pass

    def onNewJob(self, job=None, loginId=None):
        if not job:
            job = self.node.lastJob
        if job:
            if self.node == PPNODE:
                self.send({
                    'id': None,
                    'method': 'mining.notify',
                    'params': [
                        job['job_id'],
                        job['pprpcheader'],
                        '', # Don't know what exactly should go here, but t-rex
                            # miner seems to ignore this anyway and it works like
                            # this too
                        job['target'],
                        False,
                        job['height'],
                        job['bits'],
                        job['pprpcepoch'],
                        job['pprpcnextepoch'],
                        job['pprpcnextepochheight'],
                    ]
                })
            elif self.node == RXNODE:
                header = job['rxrpcheader']
                header = header[:280] + secrets.token_hex(4) + header[288:]     # Change start nonce for each client
                data = {
                    'job_id': job['job_id'],
                    'blob': header,
                    'seed_hash': reverseEndianess(job['rxrpcseed']),
                    'target': reverseEndianess(job['target'][:16]),
                    'height': job['height'],
                    'algo': 'rx/veil'
                }
                if loginId:
                    result = {
                        'id': 'rig',
                        'job': data,
                        'status': 'OK',
                        'extensions': ['algo']
                    }
                    self.send({ 'id': loginId, 'result': result, 'error': None })
                else:
                    self.send({
                        'id': None,
                        'method': 'job',
                        'params': data
                    })


def main():
    parser = argparse.ArgumentParser(prog="veilproxy",
                                     description="Stratum proxy to solo mine to VEIL node.")
    parser.add_argument('-a', '--address', default='0.0.0.0',
                        help="the address to listen on, defaults to 0.0.0.0")
    parser.add_argument('-p', '--port', type=int, required=True,
                        help="the port to listen on")
    parser.add_argument('-n', '--node', required=True,
                        help="the url of the node rpc server to connect to. " \
                             "Example: http://username:password@127.0.0.1:5555")
    parser.add_argument('-j', '--jobs', action="store_true",
                        help="show jobs in the log")
    parser.add_argument('-v', '--verbose', '--debug', action="store_true",
                        help="set log level to debug")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.0')
    args = parser.parse_args()

    global SHOW_JOBS
    SHOW_JOBS = args.jobs or args.verbose

    progpowLogger = logging.getLogger('progpow')
    randomxLogger = logging.getLogger('randomx')

    level = 'DEBUG' if args.verbose else 'INFO'
    coloredlogs.install(level=level, milliseconds=True)
    coloredlogs.install(logger=progpowLogger, level=level, milliseconds=True)
    coloredlogs.install(logger=randomxLogger, level=level, milliseconds=True)

    global PPNODE, RXNODE
    PPNODE = PPNodeConnection(args.node, progpowLogger)
    RXNODE = RXNodeConnection(args.node, randomxLogger)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    coro = loop.create_server(ServerProtocol, args.address, args.port)
    server = loop.run_until_complete(coro)

    logging.info('Serving on {}:{}'.format(*server.sockets[0].getsockname()))

    ppnode_task = loop.create_task(PPNODE.run())
    rxnode_task = loop.create_task(RXNODE.run())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        ppnode_task.cancel()
        rxnode_task.cancel()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()

if __name__ == "__main__":
    main()
