from aiohttp.web import HTTPPreconditionFailed, HTTPClientError

class LDPHTTPPreconditionFailed(HTTPPreconditionFailed):
    def __init__(self, reason=None):
        headers = {'Link': '<http://unissonco.github.io/glutton/>; rel="http://www.w3.org/ns/ldp#constrainedBy"'} # FIXME: Harcoded
        super().__init__(headers=headers, reason=reason)


class HTTPPreconditionRequired(HTTPClientError):
    status_code = 428
