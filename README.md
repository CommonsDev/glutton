Glutton
=======

An [asyncio](https://www.python.org/dev/peps/pep-3156/) implementation
of a [Linked Data Platform 1.0](http://www.w3.org/TR/ldp/) in Python.


Current Status
--------------

Working, but limited support (Create, Read, Delete. No Update yet).

You can track the progress via the
[Glutton conformance report](http://unissonco.github.io/glutton/)
generated by the
[W3C LDP Test Suite](http://w3c.github.io/ldp-testsuite/).

Requirements
------------

 * Python >= 3.4
 * pyvenv

Install
-------
 1. Create a venv with `pyvenv glutton-env`
 2. cd glutton-env
 3. source bin/activate
 4. git clone the app here
 5. cd glutton
 6. pip install -r requirements.txt

Run (development)
-----------------

### Setup a Triplestore

First, you need a
[triplestore](http://en.wikipedia.org/wiki/Triplestore) running that
speaks SPARQL 1.1 Query and Update.

I use [Fuseki](http://jena.apache.org/documentation/fuseki2/index.html)
during development. You can run it using:

  1. cd into the fuseki directory
  2. ./fuseki-server
  
If this is the first time you run it, you need to configure a dataset:

  1. Point your browser at [http://localhost:3030](http://localhost:3030)
  2. Click "Manage Datasets"
  3. Click "Add new dataset"
  4. Enter a name, e.g. "glutton"
  5. Hit "Create dataset"
  
Your SPARQL endpoints are now:

  - Query: [http://localhost:3030/glutton/query](http://localhost:3030/glutton/query)
  - Update: [http://localhost:3030/glutton/update](http://localhost:3030/glutton/update)
  
### Running Glutton

From the repository, in the glutton folder (NOT the toplevel one),
launch:

    api_hour -ac glutton:Container


Authors
-------

 - Guillaume Libersat (glibersat@sigill.org)
