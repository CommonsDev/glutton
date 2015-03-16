import asyncio

from rdflib import Graph, ConjunctiveGraph, Dataset

import SPARQLWrapper
# SPARQLWrapper.Wrapper._returnFormatSetting = [] # DIRTY HACK for 4store

@asyncio.coroutine
def connect(uri):
    g = Dataset("SPARQLUpdateStore")
    g.open(uri)

    return g
