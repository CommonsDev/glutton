import json
from pyramid.response import Response

class RDFRenderer:
    content_type = None
    rdflib_format = None

    def __init__(self, info):
        """ Constructor: info will be an object having the
        following attributes: name (the renderer name), package
        (the package that was 'current' at the time the
        renderer was registered), type (the renderer type
        name), registry (the current application registry) and
        settings (the deployment settings dictionary). """

    def __call__(self, value, system):
        """ Call the renderer implementation with the value
        and the system value passed in as arguments and return
        the result (a string or unicode object).  The value is
        the return value of a view.  The system value is a
        dictionary containing available system values
        (e.g. view, context, and request). """
        request = system.get("request")
        request.response.content_type = self.content_type

        ldpr_ref, graph = value
        rendered_value = graph.serialize(format=self.rdflib_format, base=ldpr_ref)

        return rendered_value

class JSONLDRenderer(RDFRenderer):
    content_type = "application/ld+json"
    rdflib_format = "json-ld"

class TurtleRenderer(RDFRenderer):
    content_type = "text/turtle"
    rdflib_format = "turtle"

class HTMLRenderer(RDFRenderer):
    content_type = "text/plain"
    rdflib_format = "turtle"
