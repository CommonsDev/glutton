import asyncio

@asyncio.coroutine
def cors_factory(app, handler):
    """
    Stupid CORS middleware that allows every request
    """
    @asyncio.coroutine
    def middleware(request):
        response = (yield from handler(request))
        response.headers.add('Access-Control-Allow-Origin', "*")
        return response
    return middleware
