import uuid

from rdflib import Graph, Namespace
from rdflib import URIRef, BNode, Literal
from rdflib.namespace import RDF, FOAF

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPCreated,
    HTTPClientError,
    HTTPMethodNotAllowed
    )
from pyramid.response import Response
from pyramid.view import view_config, view_defaults


from .decorators import ldpr_headers
from .deserializers import turtle_to_graph

@view_config(route_name='home', renderer='templates/mytemplate.pt')
def my_view(request):
    return {'project': 'dataserver2'}


LDP = Namespace(u"http://www.w3.org/ns/ldp#")

@view_defaults(route_name='rdfsource', decorator=(ldpr_headers,), request_method=())
class LDPRDFSourceResourceView(object):
    def __init__(self, request):
        self.request = request

        self.graph = Graph('Sleepycat', identifier='urn:my:graph')
        self.graph.open('myRDFLibStore', create=True)

        # Check if there is a root LDPC, otherwise create it
        root_ldpc = (URIRef("http://localhost:6543/r/"), RDF.type, LDP.BasicContainer)
        if not root_ldpc in self.graph:
            self.graph.add(root_ldpc)

    @view_config(accept="text/html", renderer="html", request_method=('GET', 'HEAD', 'OPTIONS'))
    @view_config(accept='application/ld+json', renderer='jsonld', request_method=('GET', 'HEAD', 'OPTIONS'))
    @view_config(accept='text/turtle', renderer='turtle', request_method=('GET', 'HEAD', 'OPTIONS'))
    def get(self):
        """
        Output a graph node (either LDPR or LDPRC) as RDF
        """
        requested_node = URIRef(self.request.path_url)

        response_graph = Graph()

        # Retrieve nodes
        if not (requested_node, None, None) in self.graph:
            return HTTPNotFound('There is no such resource')

        # if we are an LDPC, set the required header
        if (requested_node, RDF.type, LDP.BasicContainer) in self.graph:
            self.request.response.headers.add("Link", "<%s>; rel=\"type\"" % str(LDP.BasicContainer))

        response_graph += self.graph.triples((requested_node, None, None))

        return response_graph

    @view_config(accept='text/turtle', request_method=('POST',))
    def post(self):
        # Should only be allowed inside LDPC
        ldpc_ref = URIRef(self.request.path_url)

        # Refuse resource creation if we're not on a LDPC
        # FIXME: Should return 404 if not exist instead of NotAllowed
        if not (ldpc_ref, RDF.type, LDP.BasicContainer) in self.graph:
            raise HTTPMethodNotAllowed()

        # Compute a potentiel future name
        # FIXME: should consider "Slug" header
        ldpr_ref = ldpc_ref + unicode(uuid.uuid4())

        # Parse input file
        data_graph = Graph()
        try:
            # Use ldpr_ref as publicID so the "null relative URI" matches the future ldpr reference
            data_graph.parse(data=self.request.body, publicID=ldpr_ref, format="text/turtle")

            if not (ldpr_ref, None, None) in data_graph:
                raise Exception # FIXME better
        except ValueError, e:
            return HTTPClientError(e)

        # Save this document in the graph and add containment
        self.graph += data_graph.triples((ldpr_ref, None, None))
        self.graph.add((ldpc_ref, LDP.contains, ldpr_ref))

        return HTTPCreated(location=ldpr_ref)

    #@view()
    #def delete(self):
    #    requested_node = URIRef(self.request.path_url)
    #
    #    self.graph.remove((requested_node, None, None))
    #
    #    return ""
