import argparse
import asyncio
import aiohttp
import json
import random
import secrets
import string
import logging
import coloredlogs

coloredlogs.install()


def prune0x(s):
    return s[2:] if s.startswith('0x') else s


class NodeConnection:
    def __init__(self, url):
        self.url = url
        self.lastJob = None
        self.session = None
        self.subscribers = []
        self.submissionCounter = 0
        self.successfulSubmissionCounter = 0

    async def run(self):
        async with aiohttp.ClientSession() as self.session:
            while True:
                try:
                    data = {
                        'jsonrpc': '1.0',
                        'method': 'getblocktemplate',
                        'params': [],
                    }
                    async with self.session.post(self.url, json=data) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data['error']:
                                logging.error('RPC error (%d): %s',
                                              data['error']['code'],
                                              data['error']['message'])
                            else:
                                job = data['result']
                                if not self.lastJob or job['longpollid'] != self.lastJob['longpollid']:
                                    self.lastJob = job
                                    for s in self.subscribers:
                                        try:
                                            s.onNewJob(job)
                                        except asyncio.CancelledError:
                                            raise
                                        except Exception:
                                            pass
                        elif resp.status == 401:
                            logging.critical('RPC error: Unauthorized. Wrong username/password?')
                            await asyncio.sleep(10)
                        else:
                            logging.critical('Unknown RPC error: status code ' + str(resp.status))
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logging.error('RPC error: %s', str(e))
                    await asyncio.sleep(1)
                await asyncio.sleep(0.1)

    @property
    def countersStr(self):
        failedSubmissionCount = self.submissionCounter - self.successfulSubmissionCounter
        ff = '\x1b[31m{}\x1b[0m' if failedSubmissionCount > 0 else '{}'
        return '(\x1b[32m{}\x1b[0m/' + ff + ')'.format(
            self.successfulSubmissionCounter, failedSubmissionCount)

    async def submit(self, header_hash, mix_hash, nonce):
        self.submissionCounter += 1
        try:
            data = {
                'jsonrpc': '1.0',
                'method': 'pprpcsb',
                'params': [header_hash, mix_hash, nonce],
            }
            if logging.isEnabledFor(logging.DEBUG):
                logging.debug('Submitting block to node %s', json.dumps(data))
            async with self.session.post(self.url, json=data) as resp:
                res = await resp.json()
                if logging.isEnabledFor(logging.DEBUG):
                    logging.debug('Block submission response %s', json.dumps(res))
                if 'result' in res:
                    if res['result'] is True:
                        self.successfulSubmissionCounter += 1
                        logging.info('\x1b[32mBlock submission succeeded\x1b[0m %s',
                                     self.countersStr)
                        return True
                    elif res['result']:
                        logging.error('Block submission failed: %s', str(res['result']))
                        return { 'code': 26, 'message': res['result'] }
                if 'error' in res:
                    logging.error('Block submission failed (%d): %s',
                                  res['error']['code'], res['error']['message'])
                    return res['error']
                logging.error('Unknown block submission error')
                return { 'code': 25, 'message': 'Unknown error' }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.error('Block submission RPC error: %s', str(e))
            return { 'code': 24, 'message': str(e) }


class ServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.client_addr   = transport.get_extra_info('peername')
        self.transport     = transport
        self.ids           = None
        logging.info('Connection with client %s:%d established', *self.client_addr)

    def connection_lost(self, exception):
        logging.info('Connection with client %s:%d closed.', *self.client_addr)

        if self.ids:
            NODE.subscribers.remove(self)

    def send(self, data):
        data['jsonrpc'] = '2.0'
        self.transport.write(json.dumps(data).encode() + b'\n')

    async def submit(self, id, header_hash, mix_hash, nonce):
        res = await NODE.submit(header_hash, mix_hash, nonce)
        if res == True:
            self.send({ 'id': id, 'result': True })
        else:
            self.send({ 'id': id, 'result': False, 'error': res })

    def data_received(self, data):
        try:
            d = json.loads(data)
            id = d['id'] if 'id' in d else None
            if 'method' in d and 'params' in d:
                if d['method'] == 'mining.submit':
                    if len(d['params']) == 5:
                        jobId = d['params'][1]
                        nonce = prune0x(d['params'][2])
                        header_hash = prune0x(d['params'][3])
                        mix_hash = prune0x(d['params'][4])
                        if NODE.lastJob and NODE.lastJob['pprpcheader'] == jobId:
                            asyncio.ensure_future(self.submit(id, header_hash, mix_hash, nonce))
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
                elif d['method'] == 'mining.subscribe':
                    if not self.ids:
                        self.ids = [''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(13)),
                                    secrets.token_hex(2)]
                        self.send({ 'id': id, 'result': self.ids, 'error': None })

                        NODE.subscribers.append(self)
                        self.onNewJob()
                    else:
                        self.send({
                            'id': id,
                            'error': { 'code': 21, 'message': 'Already subscribed.' }
                        })
                elif d['method'] == 'mining.authorize' or d['method'] == 'mining.extranonce.subscribe':
                    self.send({ 'id': id, 'result': True, 'error': None })
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

    def onNewJob(self, job=None):
        if not job:
            job = NODE.lastJob
        if job:
            self.send({
                'id': None,
                'method': 'mining.notify',
                'params': [
                    job['pprpcheader'],
                    job['pprpcheader'],
                    '', # Don't know what exactly should go here, but t-rex
                        # miner seems to ignore this anyway and it works like
                        # this too
                    job['target'],
                    False,
                    job['height'],
                    job['bits'],
                ]
            })


def main():
    parser = argparse.ArgumentParser(description="Stratum proxy to solo mine to VEIL node.")
    parser.add_argument('-a', '--address', default='0.0.0.0',
                        help="the address to listen on, defaults to 0.0.0.0")
    parser.add_argument('-p', '--port', type=int, required=True,
                        help="the port to listen on")
    parser.add_argument('-n', '--node', required=True,
                        help="the url of the node rpc server to connect to. " \
                             "Example: http://username:password@127.0.0.1:5555")
    parser.add_argument('-v', '--verbose', '--debug', action="store_true",
                        help="set log level to debug")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    global NODE
    NODE = NodeConnection(args.node)

    loop = asyncio.get_event_loop()
    coro = loop.create_server(ServerProtocol, args.address, args.port)
    server = loop.run_until_complete(coro)

    logging.info('Serving on {}:{}'.format(*server.sockets[0].getsockname()))

    node_task = asyncio.ensure_future(NODE.run())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        node_task.cancel()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()

if __name__ == "__main__":
    main()
