""" Standalone webinterface for Openstack Swift. """
# -*- coding: utf-8 -*-
#pylint:disable=E1101
import time
import urlparse
import hmac
from hashlib import sha1
from swiftclient import client

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from swiftbrowser.forms import TimeForm
from swiftbrowser.utils import *
from swiftbrowser.views.containers import containerview

import swiftbrowser


@session_valid
def objectview(request, container, prefix=None):
    """ Returns list of all objects in current container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    # Users with no role use container keys
    if request.session.get('norole'):

        container_object = client.head_container(
            storage_url, auth_token, container)
        key = container_object.get('x-container-meta-temp-url-key', '')

    # Regular users use account keys
    else:

        account = client.head_account(storage_url, auth_token)
        key = account.get('x-account-meta-temp-url-key', '')

    request.session['container'] = container
    request.session['prefix'] = prefix
    request.session["key"] = key

    redirect_url = get_base_url(request)
    redirect_url += reverse('objectview', kwargs={'container': container, })

    try:
        meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    # Check CORS header - BASE_URL should be in there. Do not perform this
    # check for users with no role. No role users will not be accessing
    # containers in any way except for swiftbrowser. Hence their container has
    # the proper headers. Norole users are unable to set the header anyways.
    if meta.get(
        'x-container-meta-access-control-allow-origin'
    ) != settings.BASE_URL and not request.session.get('norole', False):

        # Add CORS headers so user can upload to this container.
        headers = {
            'X-Container-Meta-Access-Control-Expose-Headers':
            'Access-Control-Allow-Origin',
            'X-Container-Meta-Access-Control-Allow-Origin': settings.BASE_URL,
        }

        try:
            client.put_container(storage_url, auth_token, container, headers)

        except client.ClientException:
            messages.add_message(request, messages.ERROR, _(
                "Access denied, unable to set CORS header."))
            return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    read_acl = meta.get('x-container-read', '').split(',')
    public = False
    required_acl = ['.r:*', '.rlistings']


    swift_url = storage_url + '/' + container + '/'
    swift_slo_url = storage_url + '/' + container + '_segments/'
    if prefix:
        swift_url += prefix
        swift_slo_url += prefix
        redirect_url += prefix

    signature = create_formpost_signature(swift_url, key)
    slo_signature = create_formpost_signature(swift_slo_url, key)

    if [x for x in read_acl if x in required_acl]:
        public = True

    return render_to_response(
        "objectview.html",
        {
            'swift_url': swift_url,
            'swift_slo_url': swift_slo_url,
            'signature': signature,
            'slo_signature': slo_signature,
            'redirect_url': redirect_url,
            'container': container,
            'objects': objs,
            'folders': pseudofolders,
            'session': request.session,
            'prefix': prefix,
            'prefixes': prefixes,
            'base_url': base_url,
            'account': account,
            'public': public,
            'max_file_size': 5368709120,
            'max_file_count': 1,
            'expires': int(time.time() + 60 * 60 * 2),
        },
        context_instance=RequestContext(request)
    )


@ajax_session_valid
def get_object_table(request):
    """ Returns json object of all objects in current container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    container = request.session.get('container')
    prefix = request.session.get('prefix')

    try:
        meta, objects = client.get_container(
            storage_url,
            auth_token,
            container,
            delimiter='/',
            prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    return JsonResponse({
        'success': True,
        "data": {
            'container': container,
            'objects': objs,
            'folders': pseudofolders,
            'folder_prefix': prefix
        }
    })


@session_valid
def download(request, container, objectname):
    """ Download an object from Swift """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    key = unicode(request.session.get('key', '')).encode('utf-8')
    url = swiftbrowser.utils.get_temp_url(storage_url, auth_token, container,
                                          objectname, key)
    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    return redirect(url)


@session_valid
def delete_object(request, container, objectname):
    """ Deletes an object """
    try:
        delete_given_object(request, container, objectname)
        messages.add_message(request, messages.INFO, _("Object deleted."))
    except client.ClientException, e:
        messages.add_message(request, messages.ERROR, _("Access denied."))

    if objectname[-1] == '/':  # deleting a pseudofolder, move one level up
        objectname = objectname[:-1]
    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    return redirect(objectview, container=container, prefix=prefix)


@session_valid
def tempurl(request, container, objectname):
    """ Displays a temporary URL for a given container object. Provide a form
    to request a custom temporary URL. """

    # Check if tenant has a default temp time.
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    default_temp_time = get_default_temp_time(storage_url, auth_token)

    if default_temp_time:
        days_to_expiry = int(default_temp_time) / (24 * 3600)
        hours_to_expiry = (int(default_temp_time) % (24 * 3600)) / 3600
    else:
        # The time of the expiration of the tempurl can be defined through
        # the tenant's headers or a post.
        # The default is 7 days and 0 hours.
        days_to_expiry = 7
        hours_to_expiry = 0

    # If the request is a formpost, use the data from the formpost.
    if (request.POST):
        tempurl_form = TimeForm(request.POST)
        if tempurl_form.is_valid():

            days_to_expiry = float(tempurl_form.cleaned_data['days'])
            hours_to_expiry = float(tempurl_form.cleaned_data['hours'])

    # Tempurl uses expiration time in seconds to create the url
    seconds_to_expiry = int(
        days_to_expiry * 24 * 3600
        + hours_to_expiry * 60 * 60)

    time_of_expiry = time.strftime(
        '%A, %B %-d, %Y at %-I:%M%p',
        time.localtime(int(time.time()) + seconds_to_expiry)
    )

    # Expiration message for the front end.
    expires_in_message = '{0} days {1} hour(s) until {2}'.format(
        days_to_expiry,
        hours_to_expiry,
        time_of_expiry)

    container = unicode(container).encode('utf-8')
    objectname = unicode(objectname).encode('utf-8')

    key = unicode(request.session.get('key', '')).encode('utf-8')
    url = get_temp_url(storage_url, auth_token, container, objectname, key,
                       seconds_to_expiry)

    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    prefixes = prefix_list(prefix)

    tempurl_form = TimeForm()

    return render_to_response('tempurl.html',
                              {'url': url,
                               'account': storage_url.split('/')[-1],
                               'container': container,
                               'prefix': prefix,
                               'prefixes': prefixes,
                               'objectname': objectname,
                               'session': request.session,
                               'tempurl_form': tempurl_form,
                               'expires_in_message': expires_in_message,
                               },
                              context_instance=RequestContext(request))


@session_valid
def object_expiry(request, container, objectname):
    """ Display object's expiry date if set. Provides form to set object's
    expiry. """

    # Check if tenant has a default temp time.
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    object_expiry_time = get_object_expiry_time(
        storage_url,
        auth_token,
        container,
        objectname)

    if object_expiry_time:
        expiry_status = "This object is set to expire at " + time.strftime(
            '%A, %B %-d, %Y at %-I:%M%p',
            time.localtime(float(object_expiry_time))
        )
        days_to_expiry = (
            int(object_expiry_time) - int(time.time())
        ) / (24 * 3600)
        hours_to_expiry = (
            (int(object_expiry_time) - int(time.time())) % (24 * 3600)
        ) / 3600
    else:
        expiry_status = "false"
        days_to_expiry = 0
        hours_to_expiry = 0

    form = TimeForm(
        initial={
            'days': days_to_expiry,
            'hours': hours_to_expiry,
        }
    )

    return render_to_response(
        'object_expiry.html',
        {
            'account': storage_url.split('/')[-1],
            'container': container,
            'expiry_status': expiry_status,
            'objectname': objectname,
            'form': form
        },
        context_instance=RequestContext(request))


@session_valid
def public_objectview(request, account, container, prefix=None):
    """ Returns list of all objects in current container. """
    storage_url = settings.STORAGE_URL + account
    auth_token = ' '
    try:
        _meta, objects = client.get_container(
            storage_url,
            auth_token,
            container,
            delimiter='/',
            prefix=prefix
        )

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    return render_to_response(
        "publicview.html",
        {
            'container': container,
            'objects': objs,
            'folders': pseudofolders,
            'prefix': prefix,
            'prefixes': prefixes,
            'base_url': base_url,
            'storage_url': storage_url,
            'account': account,
        },
        context_instance=RequestContext(request)
    )
