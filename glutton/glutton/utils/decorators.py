from aiohttp.web import HTTPNotModified, HTTPNotFound
import hashlib

from ..services.data import ldpr_modification_date, node_exists, node_is_deleted, node_has_type

from .exceptions import LDPHTTPConditionFailed
from .namespace import LDP
from .misc import get_ldpr_from_request

def ldp_server_headers(view):
    """
    Standard LDP Server headers
    """
    def wrapped(instance, request):
        response = yield from view(instance, request)
        response.headers.add('Link', "<http://www.w3.org/ns/ldp#Resource>; rel=\"type\"")
        return response

    return wrapped

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
            print("current etag " + current_etag)

        # If we have an etag, Check if we match condition before processing request
        if current_etag:
            if_match = request.headers.get('If-Match')
            if_none_match = request.headers.get('If-None-Match')

            print("if match " + str(if_match))
            print("if none match " + str(if_none_match))

            if if_match:
                etag_list = [tag.strip() for tag in if_match.split(',')]
                if current_etag not in etag_list and '*' not in etag_list:
                    raise LDPHTTPConditionFailed(reason="Etag don't match.")
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

        # Check if this is a LPDC. If so, allow POST.
        container = request.app['ah_container']
        ldpr_ref = get_ldpr_from_request(request)

        # Get latest modification date (dcterms.modified)
        is_ldpc = yield from node_has_type(container, ldpr_ref, LDP.Container)

        allowed_methods = list(instance.allowed_methods)
        if not is_ldpc:
            allowed_methods.remove('POST')

        # HTTP Methods capabilities
        response.headers.add("Allow", ", ".join(allowed_methods)) # FIXME

        # HTTP POST Allowed formats
        if 'POST' in allowed_methods:
            response.headers.add('Accept-post', ", ".join(instance.accepted_post_formats))

        # HTTP PATCH Allowed formats
        if 'PATCH' in allowed_methods:
            response.headers.add('Accept-patch', ", ".join(instance.accepted_post_formats))

        return response
    return wrapper
