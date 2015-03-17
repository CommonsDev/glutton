import asyncio
import base64
import logging
from urllib.parse import urljoin

from aiohttp.multidict import CIMultiDict
from aiohttp.web import Response
from aiohttp.web import HTTPNotFound, HTTPMethodNotAllowed, HTTPCreated, HTTPNotAcceptable
from aiohttp.web import HTTPUnsupportedMediaType
from rdflib import Graph
from rdflib.namespace import RDF
from rdflib.term import URIRef
from slugify import UniqueSlugify
import uuid

from ..services.data import get_ldpc_content, ldpr_new, ldpr_delete
from ..services.data import node_exists, node_has_type
from ..utils.decorators import method_capabilities_headers, etag
from ..utils.misc import (get_hashid_for_node, get_node_by_hashid,
                          resolve_accept_header_to_rdflib_format,
                          get_ldpr_from_request)
from ..utils.namespace import LDP

LOG = logging.getLogger(__name__)

class RDFGraphResponse(Response):
    """
    Serialize graph to required format
    """
    def __init__(self, graph, accept_header='text/turtle', status=200, reason=None, headers=None):
        selected_content_type, selected_format = resolve_accept_header_to_rdflib_format(accept_header)
        headers.add('Content-type', selected_content_type)

        body = graph.serialize(format=selected_format) # FIXME: Should use uJSON

        super().__init__(body=body, status=status, reason=reason,
                         headers=headers, content_type=selected_content_type)

class LDPRDFSourceResourceView(object):
    allowed_methods = ('POST', 'GET', 'OPTIONS', 'HEAD')
    accepted_post_formats = ('text/turtle', 'application/ld+json')

    @asyncio.coroutine
    def delete(self, request):
        """
        Delete triples
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)
        print(ldpr_ref)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        if not exists:
            return HTTPNotFound(reason='There is no such resource')

        res = yield from ldpr_delete(container, ldpr_ref) # FIXME: Make sure everything is ok

        LOG.debug("delete done")
        return Response()

    @asyncio.coroutine
    @method_capabilities_headers
    def options(self, request):
        """
        Give capabilities of this LDPResource
        """
        yield
        return Response()


    @asyncio.coroutine
    def post(self, request):
        """
        Create a new LDPR inside a LDPC
        """
        container = request.app['ah_container']

        ldpc_ref = get_ldpr_from_request(request)

        has_type = yield from node_has_type(container, ldpc_ref, LDP.BasicContainer)
        if not has_type:
            raise HTTPMethodNotAllowed(method='POST', allowed_methods=('GET', 'OPTIONS', 'HEAD')) # FIXME Hardcoded

        # Compute a potentiel future slug for the newly created ldpr
        suggested_slug = request.headers.get("Slug", None)

        def is_slug_free(suggested_slug, uids):
            """
            Check if a slug is free a that LDPC
            """
            if suggested_slug in uids:
                return False
            res = yield from node_exists(container, URIRef(ldpc_ref + "/" + suggested_slug))
            return True

        slugger = UniqueSlugify(to_lower=True)
        if suggested_slug:
            # Loop while we find a free slug based on the suggestion
            # FIXME Processing time will grow with slug occupation
            future_slug = None
            while not future_slug:
                possible_slug = slugger(suggested_slug)
                exists = yield from node_exists(container, URIRef(ldpc_ref + possible_slug))
                if not exists:
                    future_slug = possible_slug
        else:
            future_slug = str(uuid.uuid4())

        ldpr_ref = ldpc_ref + "/" + future_slug

        # Parse input file
        new_graph = Graph()
        try:
            # Use ldpr_ref as publicID so the "null relative URI" matches the future ldpr reference
            requested_content_types = request.headers.get('Content-type', None)
            selected_content_type, selected_format = resolve_accept_header_to_rdflib_format(requested_content_types, fallback=False)
            if not selected_format:
                raise HTTPUnsupportedMediaType(reason="Unknown file format: {0}. Check your Content-type header.".format(requested_content_types))

            data = yield from request.text()
            new_graph.parse(data=data, publicID=ldpr_ref, format=selected_format)

            if not (ldpr_ref, None, None) in new_graph:
                raise ValueError("Document does not contains data for this LDPR") # FIXME better

        except ValueError as e:
            return HTTPNotAcceptable(reason=str(e))

        # Now we have the file as a temporary graph, store it to the backstore
        yield from ldpr_new(container, ldpr_ref, new_graph, ldpc_ref)

        headers = CIMultiDict([('Location', ldpr_ref)])
        return HTTPCreated(headers=headers)

    @asyncio.coroutine
    @etag
    @method_capabilities_headers
    def head(self, request):
        """
        Output headers of GET

        FIXME: This should not output the whole content but rather save
        time by not loading all the data.
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        if not exists:
            raise HTTPNotFound(reason='There is no such resource')

        response_graph = Graph()
        for triple in get_ldpc_content(container, ldpr_ref):
            response_graph.add(triple)

        headers = CIMultiDict([('Link', "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")])

        if (ldpr_ref, RDF.type, LDP.BasicContainer) in response_graph:
            headers.add('Link', "<http://www.w3.org/ns/ldp#BasicContainer>; rel=\"type\"")

        accept_header = request.headers.get('Accept', None)
        return RDFGraphResponse(response_graph, accept_header, headers=headers)

    @asyncio.coroutine
    @etag
    @method_capabilities_headers
    def get(self, request):
        """
        Output a graph node (either LDPR or LDPRC) as RDF
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        if not exists:
            raise HTTPNotFound(reason='There is no such resource')

        response_graph = Graph()
        for triple in get_ldpc_content(container, ldpr_ref):
            response_graph.add(triple)

        headers = CIMultiDict([('Link', "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")])

        if (ldpr_ref, RDF.type, LDP.BasicContainer) in response_graph:
            headers.add('Link', "<http://www.w3.org/ns/ldp#BasicContainer>; rel=\"type\"")

        accept_header = request.headers.get('Accept', None)
        return RDFGraphResponse(response_graph, accept_header, headers=headers)
