from aiohttp.web import HTTPPreconditionFailed, HTTPClientError, HTTPConflict

constrainedby_header = {'Link': '<http://unissonco.github.io/glutton/>; rel="http://www.w3.org/ns/ldp#constrainedBy"'} # FIXME: Harcoded

class LDPHTTPConditionFailed(HTTPClientError):
    status_code = 412
    def __init__(self, reason=None):
        super().__init__(headers=constrainedby_header, reason=reason)

class LDPHTTPConflict(HTTPConflict):
    def __init__(self, reason=None):
        super().__init__(headers=constrainedby_header, reason=reason)

class HTTPPreconditionRequired(HTTPClientError):
    status_code = 428
