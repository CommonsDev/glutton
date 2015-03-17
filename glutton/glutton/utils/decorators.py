from aiohttp.web import HTTPNotModified, HTTPNotFound
import hashlib

from ..services.data import ldpr_modification_date, node_exists, node_is_deleted

from .exceptions import LDPHTTPPreconditionFailed
from .misc import get_ldpr_from_request

def ldpr_exists_or_404(view):
    """
    raise exception if not exist or was deleted
    """
    def wrapped(instance, request):
        container = request.app['ah_container']

        ldpr_ref = get_ldpr_from_request(request)

        # Check if current node exist
        exists = yield from node_exists(container, ldpr_ref)
        deleted = yield from node_is_deleted(container, ldpr_ref)
        if not exists or deleted:
            raise HTTPNotFound(reason='There is no such resource')

        response = yield from view(instance, request)

        return response

    return wrapped

def check_weak_etag(view):
    """
    Generate an Etag header for a given response
    """
    def wrapped(instance, request):
        # Base weak etag on the modification date
        container = request.app['ah_container']
        ldpr_ref = get_ldpr_from_request(request)

        current_etag = None

        # Get latest modification date (dcterms.modified)
        modification_date = yield from ldpr_modification_date(container, ldpr_ref)
        if modification_date:
            current_etag = 'W/"{0}"'.format(hashlib.md5(modification_date).hexdigest())

        # If we have an etag, Check if we match condition before processing request
        if current_etag:
            if_match = request.headers.get('If-Match')
            if_none_match = request.headers.get('If-None-Match')

            if if_match:
                etag_list = [tag.strip() for tag in if_match.split(',')]
                if current_etag not in etag_list and '*' not in etag_list:
                    raise LDPHTTPPreconditionFailed(reason="Etag don't match.")
            elif if_none_match:
                etag_list = [tag.strip() for tag in if_none_match.split(',')]
                if current_etag in etag_list or '*' in etag_list:
                    raise HTTPNotModified()

        # Process request
        response = yield from view(instance, request)

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

        # HTTP POST Allowed formats
        if 'PATCH' in instance.allowed_methods:
            response.headers.add('Accept-patch', ", ".join(instance.accepted_post_formats))


        #response.md5_etag()
        return response
    return wrapper
