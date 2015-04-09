import logging
import asyncio

import aiohttp.web

import api_hour

from .engines import rdf
from .utils.middlewares import cors_factory
from . import endpoints

LOG = logging.getLogger(__name__)

class Container(api_hour.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.config is None: # Remove this line if you don't want to use API-Hour config file
            raise ValueError('An API-Hour config dir is needed.')

        ## Servers
        # You can define several servers, to listen HTTP and SSH for example.
        # If you do that, you need to listen on two ports with api_hour --bind command line.
        self.servers['http'] = aiohttp.web.Application(middlewares=[cors_factory], loop=kwargs['loop'])
        self.servers['http']['ah_container'] = self # keep a reference to Container
        # routes

        ldprRDF_routes = endpoints.index.LDPRDFSourceResourceView()
        self.servers['http'].router.add_route('GET',
                                              r'/{path:.*}',
                                              ldprRDF_routes.get)

        self.servers['http'].router.add_route('HEAD',
                                              r'/{path:.*}',
                                              ldprRDF_routes.head)


        self.servers['http'].router.add_route('DELETE',
                                              r'/{path:.*}',
                                              ldprRDF_routes.delete)


        self.servers['http'].router.add_route('OPTIONS',
                                              r'/{path:.*}',
                                              ldprRDF_routes.options)


        self.servers['http'].router.add_route('POST',
                                              r'/{path:.*}',
                                              ldprRDF_routes.post)

        self.servers['http'].router.add_route('PATCH',
                                              r'/{path:.*}',
                                              ldprRDF_routes.patch)

        self.servers['http'].router.add_route('PUT',
                                              r'/{path:.*}',
                                              ldprRDF_routes.put)


    def make_servers(self):
        # This method is used by api_hour command line to bind each server on each socket
        return [self.servers['http'].make_handler(logger=self.worker.log,
                                                  keep_alive=self.worker.cfg.keepalive,
                                                  access_log=self.worker.log.access_log,
                                                  access_log_format=self.worker.cfg.access_log_format)]

    @asyncio.coroutine
    def start(self):
        yield from super().start()
        LOG.info('Starting engines...')

        if 'triplestore' in self.config['engines']:
            ts_config = self.config['engines']['triplestore']
            self.engines['triplestore'] = self.loop.create_task(rdf.connect(driver=ts_config['driver'],
                                                                            uri=ts_config['uri'])) # FIXME: A pool should be created

        yield from asyncio.wait([self.engines['triplestore']], return_when=asyncio.ALL_COMPLETED)

        LOG.info('All engines ready !')


    @asyncio.coroutine
    def stop(self):
        LOG.info('Stopping engines...')

        # FIXME : Should stop the triplestore here

        LOG.info('All engines stopped !')
        yield from super().stop()
