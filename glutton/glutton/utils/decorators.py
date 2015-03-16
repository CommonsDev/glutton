import hashlib

def etag(view): # Ripped from SANDMAN
    """
    Generate an Etag header for a given response
    """
    def wrapped(*args, **kwargs):
        # only for HEAD and GET requests
        response = yield from view(*args, **kwargs)
        etag = '"' + hashlib.md5(response.text.encode('utf-8')).hexdigest() + '"'
        response.headers.add('ETag', etag)
        # FIXME Port later!
        # if_match = request.headers.get('If-Match')
        # if_none_match = request.headers.get('If-None-Match')
        # if if_match:
        #     etag_list = [tag.strip() for tag in if_match.split(',')]
        #     if etag not in etag_list and '*' not in etag_list:
        #         rv = precondition_failed()
        # elif if_none_match:
        #     etag_list = [tag.strip() for tag in if_none_match.split(',')]
        #     if etag in etag_list or '*' in etag_list:
        #         rv = not_modified()
        return response
    return wrapped

def method_capabilities_headers(view):
    """
    Add "Allow:" and "Accept-post:" headers.
    """
    def wrapper(instance, request):
        #request.response.headers.add("Link", "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")

        response = yield from view(instance, request)

        # HTTP Methods capabilities
        response.headers.add("Allow", ", ".join(instance.allowed_methods)) # FIXME

        # HTTP POST Allowed formats
        if 'POST' in instance.allowed_methods:
            response.headers.add('Accept-post', ", ".join(instance.accepted_post_formats))

        #response.md5_etag()
        return response
    return wrapper
