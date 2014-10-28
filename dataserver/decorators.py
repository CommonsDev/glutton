def ldpr_headers(view):
    def wrapper(root, request):
        request.response.headers.add("Link", "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")
        request.response.headers.add("Allow", "GET, OPTIONS, HEAD, POST") # FIXME
        request.response.headers.add("Accept-Post", "text/turtle") # FIXME
        response = view(root, request)
        response.md5_etag()
        return response
    return wrapper
