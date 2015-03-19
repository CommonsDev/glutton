import asyncio
import logging

from rdflib import URIRef, Namespace, Literal
from rdflib.namespace import RDF

from .data import node_has_type
from ..utils.namespace import LDP

LOG = logging.getLogger(__name__)

"""
Non RDF Handling
"""
@asyncio.coroutine
def ldpr_nr_new(container, data, ldpc_ref=None):
    """
    Add a new NR resource (binary) to a LDPC
    """
    store = yield from container.engines['triplestore']

    depot = container.filedepot
    fileid = depot.create(data)
    stored_file = depot.get(fileid)

    ldpr_uri = stored_file.public_url # FIXME Can return None depending on backend, Warning!
    if not ldpr_uri:
        LOG.error("BACKEND DOESN'T SUPPORT PUBLIC URI")
        ldpr_uri = "http://localhost:8000/depot/default/" + fileid


    if ldpc_ref:
        # Make the ldpc_ref a LDPC if not already one
        ldpc_ref_is_already_a_ldpc = yield from node_has_type(container, ldpc_ref, LDP.Container)
        if not ldpc_ref_is_already_a_ldpc:
            store.add((ldpc_ref, RDF.type, LDP.Container))
            store.add((ldpc_ref, RDF.type, LDP.RDFSource))
            store.add((ldpc_ref, RDF.type, LDP.BasicContainer))

        # Add this LDPR to the LDPC if specified
        store.add((ldpc_ref, LDP.contains, URIRef(ldpr_uri)))
        # FIXME: Should update "modified" field on LDPC
        LOG.debug("Added LDPR NR {0} to LDPC {1}".format(ldpr_uri, ldpc_ref))

    LOG.debug("Made new LDPR NR {0}".format(ldpr_uri))

    return ldpr_uri
