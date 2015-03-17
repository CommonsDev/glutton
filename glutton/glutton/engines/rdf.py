import asyncio

from rdflib import Dataset

@asyncio.coroutine
def connect(driver, uri):
    g = Dataset(driver)
    if type(uri) == list:
        uri = tuple(uri)
    g.open(uri)
    return g
