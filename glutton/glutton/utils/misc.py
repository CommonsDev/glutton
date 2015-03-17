from urllib.parse import urljoin

from hashids import Hashids
from rdflib.term import URIRef
from webob.acceptparse import Accept

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
