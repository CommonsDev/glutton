from urllib.parse import urljoin

from aiohttp.web import HTTPUnsupportedMediaType, HTTPNotAcceptable
from hashids import Hashids
from rdflib.term import URIRef
from webob.acceptparse import Accept

from .namespace import LDP

### HASHING
def get_hashid_for_node(node):
    """
    Given a Node, return a string hash
    """
    hashids = Hashids(salt="xx") # FIXME
    byte_array = list(bytearray(node, 'utf-8'))
    return hashids.encode(*byte_array)

def get_node_by_hashid(hashid):
    """
    Resolve a hash to a RDF Node
    """
    hashids = Hashids(salt="xx") # FIXME
    decoded_array = hashids.decode(hashid)
    return URIRef(bytes(decoded_array).decode('utf-8'))

### Graph reading
def feed_graph_from_request(ldpr_ref, graph, request):
    # Use ldpr_ref as publicID so the "null relative URI" matches the future ldpr reference
    requested_content_types = request.headers.get('Content-type', None)
    selected_content_type, selected_format = resolve_accept_header_to_rdflib_format(requested_content_types, fallback=False)
    if not selected_format:
        raise HTTPUnsupportedMediaType(reason="Unknown file format: {0}. Check your Content-type header.".format(requested_content_types))

    data = yield from request.text()
    print("====")
    print(data)
    print("====")
    graph.parse(data=data, publicID=ldpr_ref, format=selected_format)

    if not (ldpr_ref, None, None) in graph:
        raise HTTPNotAcceptable(reason="Document does not contains data for this LDPR") # FIXME Is that the correct HTTP error?

    return graph


### HTTP
def get_ldpr_from_request(request):
    return URIRef(urljoin("http://" + request.host, request.path).rstrip("/")) # HTTP Hardcoded, what about ssl?

### RDFLIB
def resolve_accept_header_to_rdflib_format(accept_header, fallback=True, fallback_format=('text/turtle', 'n3')):
    """
    Given an HTTP Accept: header, return an RDFLib acceptable format for serializing
    """
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
