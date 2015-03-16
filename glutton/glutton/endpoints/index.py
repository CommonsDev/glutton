import hashlib
import functools
from pprint import pprint
import logging
import asyncio
import aiohttp.web

from slugify import UniqueSlugify
import uuid

from rdflib.term import URIRef
from hashids import Hashids
import base64

from api_hour.plugins.aiohttp import JSON



from rdflib import Namespace

LDP = Namespace("http://www.w3.org/ns/ldp#")


LOG = logging.getLogger(__name__)


from aiohttp.web import HTTPNotFound, HTTPMethodNotAllowed, HTTPCreated, HTTPNotAcceptable
from aiohttp.web import HTTPUnsupportedMediaType
from aiohttp.multidict import CIMultiDict
from ..services.data import get_model_subjects, get_subject_value, get_ldpc_content
from ..services.data import node_exists, node_has_type, ldpr_new, ldpr_delete

import rdflib
from rdflib.namespace import FOAF, RDF

person_model = {
    'ontology': FOAF.Person,
    'fields': {
        'full_name': FOAF.name,
        'first_name': FOAF.firstName,
        'last_name': FOAF.familyName,
        'nick': FOAF.nickname
    }
}

def get_hashid_for_node(node):
    hashids = Hashids(salt="xx") # FIXME
    byte_array = list(bytearray(node, 'utf-8'))
    return hashids.encode(*byte_array)

def get_node_by_hashid(hashid):
    hashids = Hashids(salt="xx") # FIXME
    decoded_array = hashids.decode(hashid)
    return URIRef(bytes(decoded_array).decode('utf-8'))

def method_capabilities_headers(view):
    def wrapper(instance, request):
        #request.response.headers.add("Link", "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")

        response = yield from view(instance, request)

        # HTTP Methods capabilities
        response.headers.add("Allow", ", ".join(instance.allowed_methods)) # FIXME

        # HTTP POST Allowed formats
        if 'POST' in instance.allowed_methods:
            response.headers.add('Accept-post', ", ".join(instance.accepted_post_formats))

        #response.md5_etag()
        return response
    return wrapper

from aiohttp.web import Response
from rdflib import Graph

from webob.acceptparse import Accept

def resolve_accept_header_to_rdflib_format(accept_header, fallback=True, fallback_format=('text/turtle', 'n3')):
    content_type_mapping = {
        'application/ld+json': 'json-ld',
        'text/turtle': 'n3'
    }

    server_offer = (
        ('text/turtle', 1),
        ('application/ld+json', 0.8)
    )

    accept = Accept(accept_header)
    content_type_match = accept.best_match(server_offer)

    if content_type_match:
        return (content_type_match, content_type_mapping[content_type_match])
    else:
        if fallback:
            return fallback_format

    return (None, None)


class RDFGraphResponse(Response):
    """
    Serialize graph to required format
    """
    def __init__(self, graph, accept_header='text/turtle', status=200, reason=None, headers=None):
        selected_content_type, selected_format = resolve_accept_header_to_rdflib_format(accept_header)
        headers.add('Content-type', selected_content_type)

        body = graph.serialize(format=selected_format)

        super().__init__(body=body, status=status, reason=reason,
                         headers=headers, content_type=selected_content_type)

def etag(view): # Ripped from SANDMAN
    def wrapped(*args, **kwargs):
        # only for HEAD and GET requests
        response = yield from view(*args, **kwargs)
        etag = '"' + hashlib.md5(response.text.encode('utf-8')).hexdigest() + '"'
        response.headers.add('ETag', etag)
        # FIXME Port later!
        # if_match = request.headers.get('If-Match')
        # if_none_match = request.headers.get('If-None-Match')
        # if if_match:
        #     etag_list = [tag.strip() for tag in if_match.split(',')]
        #     if etag not in etag_list and '*' not in etag_list:
        #         rv = precondition_failed()
        # elif if_none_match:
        #     etag_list = [tag.strip() for tag in if_none_match.split(',')]
        #     if etag in etag_list or '*' in etag_list:
        #         rv = not_modified()
        return response
    return wrapped

def get_ldpr_from_request(request):
    return URIRef("http://{0}{1}".format(request.host, request.path).rstrip("/")) # HTTP Hardcoded, what about ssl?

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


        # new_location = "http://{0}".format(ldpr_ref) # FIXME: If ssl: https
        print(ldpr_ref)
        headers = CIMultiDict([('Location', ldpr_ref)])
        return HTTPCreated(headers=headers)

    @asyncio.coroutine
    @etag
    @method_capabilities_headers
    def head(self, request):
        """
        Output headers of GET
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

@asyncio.coroutine
def rdfapi_detail(request):
    container = request.app['ah_container']
    hashid = request.match_info.get('hashid')

    model = person_model
    subject = get_node_by_hashid(hashid)
    if str(subject) in ("", None):
        raise aiohttp.web.HTTPNotFound()
    item = {'id': hashid, 'uri': subject}
    for field in model['fields']:
        item[field] = yield from get_subject_value(container, subject, predicate=model['fields'][field])

    return JSON(item)

@asyncio.coroutine
def rdfapi_list(request):
    container = request.app['ah_container']

    model = person_model

    items = []
    for subject in get_model_subjects(container, model['ontology']):
        if type(subject) == rdflib.term.BNode: # Ignore blank nodes
            continue

        item = {'id': get_hashid_for_node(subject), 'uri': subject}
        for field in model['fields']:
            item[field] = yield from get_subject_value(container, subject, predicate=model['fields'][field])
        items.append(item)

    return JSON(items)
