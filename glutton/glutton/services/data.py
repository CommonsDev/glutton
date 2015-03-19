import asyncio
from datetime import datetime
import logging

from random import randint
import rdflib
from rdflib import Graph
from rdflib.namespace import RDF, DCTERMS
from rdflib import URIRef, Namespace, Literal

from ..utils.namespace import LDP, GLUTTON

LOG = logging.getLogger(__name__)

"""
RDF Data handling
"""

@asyncio.coroutine
def node_has_type(container, subject, rdftype):
    store = yield from container.engines['triplestore']

    LOG.debug("checking if <{0}> is of type <{1}>...".format(subject, rdftype))
    return (subject, RDF.type, rdftype) in store

@asyncio.coroutine
def node_exists(container, subject):
    store = yield from container.engines['triplestore']

    LOG.debug("checking if {0} exists".format(subject))
    exists = (subject, None, None) in store

    return exists

@asyncio.coroutine
def node_is_deleted(container, subject):
    store = yield from container.engines['triplestore']

    LOG.debug("checking if {0} is deleted".format(subject))
    is_deleted = (subject, GLUTTON.deleted, None) in store

    return is_deleted

@asyncio.coroutine
def node_objects(container, subject, predicate):
    store = yield from container.engines['triplestore']

    values = set()
    for obj in store.objects(subject, predicate):
        values.add(obj)

    return values

@asyncio.coroutine
def ldpr_modification_date(container, ldpr_ref):
    store = yield from container.engines['triplestore']

    obj = store.value(None, DCTERMS.modified)

    return str(obj).encode('utf-8')

@asyncio.coroutine
def ldpr_get(container, ldpr_ref):
    store = yield from container.engines['triplestore']

    results = yield from store.triples((ldpr_ref, None, None))

    return results

@asyncio.coroutine
def ldpr_new(container, ldpr_ref, ldpr_graph, ldpc_ref=None):
    """
    Add a new resource (graph) to a LDPC
    """
    store = yield from container.engines['triplestore']

    # Mark this new LDPR as a RDF Source
    ldpr_graph.add((ldpr_ref, RDF.type, LDP.RDFSource))

    # Mark this LDPR with current modification/creation date
    now = datetime.now()
    ldpr_graph.add((ldpr_ref, DCTERMS.modified, Literal(now)))
    ldpr_graph.add((ldpr_ref, DCTERMS.created, Literal(now)))

    # Copy temp graph to datastore
    for triple in ldpr_graph.triples((ldpr_ref, None, None)):
        store.add(triple)

    if ldpc_ref:
        # Make the ldpc_ref a LDPC if not already one
        ldpc_ref_is_already_a_ldpc = yield from node_has_type(container, ldpc_ref, LDP.Container)
        if not ldpc_ref_is_already_a_ldpc:
            store.add((ldpc_ref, RDF.type, LDP.Container))
            store.add((ldpc_ref, RDF.type, LDP.RDFSource))
            store.add((ldpc_ref, RDF.type, LDP.BasicContainer))

        # Add this LDPR to the LDPC if specified
        store.add((ldpc_ref, LDP.contains, ldpr_ref))
        # FIXME: Should update "modified" field on LDPC
        LOG.debug("Added LDPR {0} to LDPC {1}".format(ldpr_ref, ldpc_ref))

    LOG.debug("Made new LDPR {0}".format(ldpr_ref))

    return True

@asyncio.coroutine
def ldpr_delete(container, ldpr_ref, mark_deleted=True, remove_containement_triples=True):
    """
    Delete a LDPR and its containement triples
    FIXME Should be transactional
    """
    store = yield from container.engines['triplestore']

    # Remove any containment triplet
    if remove_containement_triples:
        store.remove((None, LDP.contains, ldpr_ref))
        # FIXME: Should update modified field on LDPC

    # Remove actual LDPR
    store.remove((ldpr_ref, None, None))

    if mark_deleted:
        # Mark as deleted FIXME: Not sure this is the best way to do this!
        # FIXME: This is a possible race since we delete everything then add
        # a triple (and we don't use transaction)
        now = datetime.now()
        store.add((ldpr_ref, GLUTTON.deleted, Literal(now)))

    return True
