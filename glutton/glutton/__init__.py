import logging
import asyncio

import aiohttp.web
import aiopg
import psycopg2.extras

import api_hour

from .engines import rdf
from . import endpoints

from .services.data import make_root_basic_container

LOG = logging.getLogger(__name__)

class Container(api_hour.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.config is None: # Remove this line if you don't want to use API-Hour config file
            raise ValueError('An API-Hour config dir is needed.')

        ## Servers
        # You can define several servers, to listen HTTP and SSH for example.
        # If you do that, you need to listen on two ports with api_hour --bind command line.
        self.servers['http'] = aiohttp.web.Application(loop=kwargs['loop'])
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


        # uri_mapping = {
        #     'person': 'xx'
        # }

        # for mapping_name in uri_mapping:
        #     self.servers['http'].router.add_route('GET',
        #                                           '/{0}'.format(mapping_name),
        #                                           endpoints.index.rdfapi_list)
        #     self.servers['http'].router.add_route('GET',
        #                                           '/{0}/{1}'.format(mapping_name, '{hashid}'),
        #                                           endpoints.index.rdfapi_detail)



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
        # Add your custom engines here, example with PostgreSQL:
        # self.engines['pg'] = self.loop.create_task(aiopg.create_pool(host=self.config['engines']['pg']['host'],
        #                                                              port=int(self.config['engines']['pg']['port']),
        #                                                              sslmode='disable',
        #                                                              dbname=self.config['engines']['pg']['dbname'],
        #                                                              user=self.config['engines']['pg']['user'],
        #                                                              password=self.config['engines']['pg']['password'],
        #                                                              cursor_factory=psycopg2.extras.RealDictCursor,
        #                                                              minsize=int(self.config['engines']['pg']['minsize']),
        #                                                              maxsize=int(self.config['engines']['pg']['maxsize']),
        #                                                              loop=self.loop))

        self.engines['sparql'] = self.loop.create_task(rdf.connect(uri=("http://localhost:3030/ds/query", "http://localhost:3030/ds/update")))

        yield from asyncio.wait([self.engines['sparql']], return_when=asyncio.ALL_COMPLETED)

        # Make sure we have at least a basic root container
        yield from make_root_basic_container(self)


        LOG.info('All engines ready !')


    @asyncio.coroutine
    def stop(self):
        LOG.info('Stopping engines...')
        # Add your custom end here, example with PostgreSQL:
        if 'pg' in self.engines:
            if self.engines['pg'].done():
                self.engines['pg'].result().terminate()
                yield from self.engines['pg'].result().wait_closed()
            else:
                yield from self.engines['pg'].cancel()
        LOG.info('All engines stopped !')
        yield from super().stop()
