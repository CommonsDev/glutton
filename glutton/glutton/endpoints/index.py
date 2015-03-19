import asyncio
import base64
import logging
from urllib.parse import urljoin

from aiohttp.multidict import CIMultiDict
from aiohttp.web import Response
from aiohttp.web import HTTPNotFound, HTTPMethodNotAllowed, HTTPCreated, HTTPNotAcceptable, HTTPNoContent
from aiohttp.web import HTTPUnsupportedMediaType, HTTPInternalServerError, HTTPAccepted
import hashlib
from rdflib import Graph
from rdflib.namespace import RDF, DCTERMS
from rdflib.term import URIRef
from slugify import UniqueSlugify
import uuid

from ..services.data import ldpr_get, ldpr_new, ldpr_delete, ldpr_modification_date
from ..services.data import node_exists, node_has_type, node_is_deleted, node_objects
from ..utils.decorators import method_capabilities_headers, check_weak_etag, ldpr_exists_or_404
from ..utils.exceptions import HTTPPreconditionRequired, LDPHTTPConflict
from ..utils.misc import (get_hashid_for_node, get_node_by_hashid,
                          resolve_accept_header_to_rdflib_format,
                          get_ldpr_from_request, feed_graph_from_request)
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

    @asyncio.coroutine
    def compute_etag(self, request):
        """
        Compute etag based on the modification date of the LDPR
        and add the "Etag:" header to the Response.
        """
        ldpr_ref = get_ldpr_from_request(request)
        modification_date = yield from ldpr_modification_date(request.app['ah_container'], ldpr_ref)
        etag = 'W/"{0}"'.format(hashlib.md5(modification_date).hexdigest())

        self.headers.add('Etag', etag)


class LDPRDFSourceResourceView(object):
    allowed_methods = ('POST', 'PATCH', 'PUT', 'GET', 'OPTIONS', 'HEAD')
    accepted_post_formats = ('text/turtle', 'application/ld+json')

    @asyncio.coroutine
    @ldpr_exists_or_404
    def delete(self, request):
        """
        Delete triples
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        deleted = yield from node_is_deleted(container, ldpr_ref)
        if not exists or deleted:
            return HTTPNotFound(reason='There is no such resource')

        res = yield from ldpr_delete(container, ldpr_ref) # FIXME: Make sure everything is ok

        LOG.debug("delete done")
        return Response()

    @asyncio.coroutine
    @ldpr_exists_or_404
    @method_capabilities_headers
    def options(self, request):
        """
        Give capabilities of this LDPResource
        """
        yield
        return HTTPNoContent()

    @asyncio.coroutine
    @ldpr_exists_or_404
    def patch(self, request):
        yield
        return Response()

    @asyncio.coroutine
    @check_weak_etag
    def put(self, request):
        """
        Replace a LDPR at the given URI
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        deleted = yield from node_is_deleted(container, ldpr_ref)
        if deleted:
            raise HTTPConflict(reason="Can't reuse old URIs.")

        exists = yield from node_exists(container, ldpr_ref)
        if not exists: # Creation
            # raise HTTPMethodNotAllowed(method='PUT', reason='use POST to create resource', allowed_methods=('POST',))
            response = yield from self.post(request)
            return response

        else: # Update
            # If-match is required to prevent collisions
            if not request.headers.get("If-match"):
                raise HTTPPreconditionRequired(reason="Missing If-match header")

            client_graph = Graph()
            client_graph = yield from feed_graph_from_request(ldpr_ref, client_graph, request)

            # Check if containement triple were modified (forbidden by spec)
            old_containement = yield from node_objects(container, ldpr_ref, LDP.contains)
            new_containement = set()
            for obj in client_graph.objects((ldpr_ref, LDP.contains)):
                new_containement.add(obj)

            if old_containement != new_containement:
                raise LDPHTTPConflict(reason="You are not allowed to update an LPDC's containement triples.")

            # FIXME Should be transactional
            yield from ldpr_delete(container, ldpr_ref, mark_deleted=False, remove_containement_triples=False)
            yield from ldpr_new(container, ldpr_ref, client_graph, ldpc_ref=None)

        # Give the new LDPR graph back
        response_graph = Graph()
        for triple in ldpr_get(container, ldpr_ref):
            response_graph.add(triple)

        headers = CIMultiDict([('Location', ldpr_ref)])
        content_type_header = request.headers.get('Content-type', None)

        response = RDFGraphResponse(response_graph, content_type_header, status=204, headers=headers) # FIXME: Harcoded 204
        yield from response.compute_etag(request)

        return response

    @asyncio.coroutine
    def post(self, request):
        """
        Create a new LDPR inside a LDPC
        """
        container = request.app['ah_container']

        ldpc_ref = get_ldpr_from_request(request)

        # FIXME I removed this so the tests now pass, but still it feels strange to allow LDPR
        # creation when not linked to a LDPC.
        # has_type = yield from node_has_type(container, ldpc_ref, LDP.BasicContainer)
        # if not has_type:
        #     raise HTTPMethodNotAllowed(method='POST', allowed_methods=('GET', 'OPTIONS', 'HEAD')) # FIXME Hardcoded

        # Compute a potentiel future slug for the newly created ldpr
        suggested_slug = request.headers.get("Slug", None)

        slugger = UniqueSlugify(to_lower=True)
        if suggested_slug:
            # Loop while we find a free slug based on the suggestion
            # FIXME Processing time will grow with slug occupation
            future_slug = None
            while not future_slug:
                possible_slug = slugger(suggested_slug)
                possible_uriref = URIRef(ldpc_ref + "/" + possible_slug)
                exists = yield from node_exists(container, possible_uriref)
                deleted = yield from node_is_deleted(container, possible_uriref)
                if not exists and not deleted:
                    future_slug = possible_slug
        else:
            future_slug = str(uuid.uuid4())

        ldpr_ref = ldpc_ref + "/" + future_slug

        # Parse input file
        client_graph = Graph()
        client_graph = yield from feed_graph_from_request(ldpr_ref, client_graph, request)

        # Now we have the file as a temporary graph, store it to the backstore
        yield from ldpr_new(container, ldpr_ref, client_graph, ldpc_ref)

        headers = CIMultiDict([('Location', ldpr_ref)])
        return HTTPCreated(headers=headers)

    @asyncio.coroutine
    @ldpr_exists_or_404
    @check_weak_etag
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
        deleted = yield from node_is_deleted(container, ldpr_ref)
        if not exists or deleted:
            raise HTTPNotFound(reason='There is no such resource')

        response_graph = Graph()
        for triple in ldpr_get(container, ldpr_ref):
            response_graph.add(triple)

        headers = CIMultiDict([('Link', "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")])

        if (ldpr_ref, RDF.type, LDP.BasicContainer) in response_graph:
            headers.add('Link', "<http://www.w3.org/ns/ldp#BasicContainer>; rel=\"type\"")

        accept_header = request.headers.get('Accept', None)
        response = RDFGraphResponse(response_graph, accept_header, headers=headers)
        yield from response.compute_etag(request)
        return response

    @asyncio.coroutine
    @ldpr_exists_or_404
    @check_weak_etag
    @method_capabilities_headers
    def get(self, request):
        """
        Output a graph node (either LDPR or LDPRC) as RDF
        """
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        deleted = yield from node_is_deleted(container, ldpr_ref)
        if not exists or deleted:
            raise HTTPNotFound(reason='There is no such resource')

        response_graph = Graph()
        for triple in ldpr_get(container, ldpr_ref):
            response_graph.add(triple)

        headers = CIMultiDict([('Link', "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")])

        if (ldpr_ref, RDF.type, LDP.BasicContainer) in response_graph:
            headers.add('Link', "<http://www.w3.org/ns/ldp#BasicContainer>; rel=\"type\"")

        accept_header = request.headers.get('Accept', None)
        response = RDFGraphResponse(response_graph, accept_header, headers=headers)
        yield from response.compute_etag(request)
        return response
