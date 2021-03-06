### comm_server.py

from collections import deque
from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import Factory
from twisted.internet import interfaces
from zope.interface import implements

import command


class ProducerToManyClient:
    implements(interfaces.IConsumer)

    def __init__(self):
        print('initing {}'.format(self.__class__))
        self.clients = []

    def addClient(self, client):
        print('client added to one2many made')
        self.clients.append(client)

    def write(self, data):
        #print('one2many received data')
        for client in self.clients:
            client.write(data)

    def removeClient(self, client, reason):
        self.clients.remove(client)


class ProducerConsumerBufferProxy:
    """Proxy which buffers a few telemetry blocks and drops old ones"""
    implements(interfaces.IPushProducer, interfaces.IConsumer)

    def __init__(self, producer, consumer):
        print('initing {}'.format(self.__class__))
        self._paused = False
        self._buffer = deque(maxlen = 10)
        self._producer = producer
        self._consumer = consumer
        self._producer.addClient(self)
    
    def pauseProducing(self):
        print('pausing {}'.format(
            self._consumer.transport.getPeer()))
        self._paused = True

    def resumeProducing(self):
        print('resuming {}'.format(
            self._consumer.transport.getPeer()))
        self._paused = False

    def unregisterProducer(self):
        self._producer.removeClient(self)

    def stopProducing(self):
        pass

    def write(self, data):
        self._buffer.append(data)
        if not self._paused:
            for data in self._buffer:
                self._consumer.transport.write(data)
            self._buffer.clear()

class ServeTelemetry(LineReceiver):
    """Serve the telemetry"""
    def __init__(self, producer, raw_source, header):
        print('initing {}'.format(self.__class__))
        self._producer = producer
        self._is_commander = False
        self._raw_telemetry_source = raw_source
        self._header = header

    def connectionMade(self):
        self.proxy = ProducerConsumerBufferProxy(self._producer, self)
        self.transport.registerProducer(self.proxy, True)
        self.proxy.write(self._header+'\r\n')
        self.proxy.resumeProducing()

    def lineReceived(self, line):
        print('from {} received line {}'.format(
            self.transport.getPeer(), line))
        if line == 'commander':
            self._is_commander = True
        elif self._is_commander:
            valid, cmd = command.parse_command(line.rstrip())
            if valid:
                self._raw_telemetry_source.async_tx(cmd)
            else:
                print('command not valid')


    def connectionLost(self, reason):
        print('connection lost from {}'.format(self.transport.getPeer()))
        self.transport.unregisterProducer()


class TelemetryFactory(Factory):

    def __init__(self, raw_source, header):
        self.clients = []
        self._raw_source = raw_source
        self._header= header

    def setSource(self, telemetrySource):
        self._telemetrySource = telemetrySource

    def buildProtocol(self, addr):
        return ServeTelemetry(self._telemetrySource, self._raw_source, self._header)
