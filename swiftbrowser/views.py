""" Standalone webinterface for Openstack Swift. """
# -*- coding: utf-8 -*-
#pylint:disable=E1101
import os
import time
import urlparse
import hmac
from hashlib import sha1

from swiftclient import client
from django.shortcuts import render_to_response, redirect, render
from django.template import RequestContext
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseRedirect
from django.views import generic
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from jfu.http import upload_receive, UploadResponse, JFUResponse
from swiftbrowser.models import Photo
from swiftbrowser.models import Document
from swiftbrowser.forms import CreateContainerForm, PseudoFolderForm, \
                               LoginForm, AddACLForm, DocumentForm
from swiftbrowser.utils import replace_hyphens, prefix_list, \
                               pseudofolder_object_list, get_temp_key,\
                               get_base_url, get_temp_url

import swiftbrowser


def login(request):
    """ Tries to login user and sets session data """
    request.session.flush()
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        tenant = settings.SWIFT_TENANT_NAME + ":" + username
        try:
            auth_version = settings.SWIFT_AUTH_VERSION or 1
            (storage_url, auth_token) = client.get_auth(
                settings.SWIFT_AUTH_URL, tenant, password,
                auth_version=auth_version)
            request.session['auth_token'] = auth_token
            request.session['storage_url'] = storage_url
            request.session['username'] = tenant
            request.session['user'] = username
           
            return redirect(containerview)

        except client.ClientException:
            messages.add_message(request, messages.ERROR, _("Login failed."))

    return render_to_response('login.html', {'form': form, },
                              context_instance=RequestContext(request))

def containerview(request):
    """ Returns a list of all containers in current account. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        account_stat, containers = client.get_account(storage_url, auth_token)
    except client.ClientException:
        return redirect(login)

    account_stat = replace_hyphens(account_stat)

    return render_to_response('containerview.html', {
        'account_stat': account_stat,
        'containers': containers,
        'session': request.session,
    }, context_instance=RequestContext(request))


def create_container(request):
    """ Creates a container (empty object of type application/directory) """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = CreateContainerForm(request.POST or None)
    if form.is_valid():
        container = form.cleaned_data['containername']
        try:
            client.put_container(storage_url, auth_token, container)
            messages.add_message(request, messages.INFO,
                                 _("Container created."))
        except client.ClientException:
            messages.add_message(request, messages.ERROR, _("Access denied."))

        return redirect(containerview)

    return render_to_response('create_container.html', {
                    'session': request.session,
                              }, context_instance=RequestContext(request))


def delete_container(request, container):
    """ Deletes a container """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        _m, objects = client.get_container(storage_url, auth_token, container)
        for obj in objects:
            client.delete_object(storage_url, auth_token,
                                 container, obj['name'])
        client.delete_container(storage_url, auth_token, container)
        messages.add_message(request, messages.INFO, _("Container deleted."))
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))

    return redirect(containerview)


def objectview(request, container, prefix=None):
    """ Returns list of all objects in current container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    
    request.session['container'] = container   
    request.session['prefix'] = prefix
           
    try:
        meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    read_acl = meta.get('x-container-read', '').split(',')
    public = False
    required_acl = ['.r:*', '.rlistings']
    if [x for x in read_acl if x in required_acl]:
        public = True

    return render_to_response("objectview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'session': request.session,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'account': account,
        'public': public,
        },
        context_instance=RequestContext(request))

def objecttable(request):
    """ Returns list of all objects in current container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    container = request.session.get('container')
    prefix = request.session.get('prefix')
    try:
        meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    read_acl = meta.get('x-container-read', '').split(',')
    public = False
    required_acl = ['.r:*', '.rlistings']
    if [x for x in read_acl if x in required_acl]:
        public = True

    return render_to_response("object_table.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'session': request.session,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'account': account,
        'public': public,
        },
        context_instance=RequestContext(request))

def upload_form(request, container, prefix):
    
    return render_to_response('upload_form.html',{
        'container': container,
        'prefix':prefix,
    },context_instance=RequestContext(request)
    )
  

def download(request, container, objectname):
    """ Download an object from Swift """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    url = swiftbrowser.utils.get_temp_url(storage_url, auth_token,
                                          container, objectname)
    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    return redirect(url)


def delete_object(request, container, objectname):
    """ Deletes an object """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    try:
        client.delete_object(storage_url, auth_token, container, objectname)
        messages.add_message(request, messages.INFO, _("Object deleted."))
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
    if objectname[-1] == '/':  # deleting a pseudofolder, move one level up
        objectname = objectname[:-1]
    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    return redirect(objectview, container=container, prefix=prefix)


def toggle_public(request, container):
    """ Sets/unsets '.r:*,.rlistings' container read ACL """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta = client.head_container(storage_url, auth_token, container)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    read_acl = meta.get('x-container-read', '')
    if '.rlistings' and '.r:*' in read_acl:
        read_acl = read_acl.replace('.r:*', '')
        read_acl = read_acl.replace('.rlistings', '')
        read_acl = read_acl.replace(',,', ',')
    else:
        read_acl += '.r:*,.rlistings'
    headers = {'X-Container-Read': read_acl, }

    try:
        client.post_container(storage_url, auth_token, container, headers)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))

    return redirect(objectview, container=container)


def public_objectview(request, account, container, prefix=None):
    """ Returns list of all objects in current container. """
    storage_url = settings.STORAGE_URL + account
    auth_token = ' '
    try:
        _meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    return render_to_response("publicview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'storage_url': storage_url,
        'account': account,
        },
        context_instance=RequestContext(request))


def tempurl(request, container, objectname):
    """ Displays a temporary URL for a given container object """

    container = unicode(container).encode('utf-8')
    objectname = unicode(objectname).encode('utf-8')

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    url = get_temp_url(storage_url, auth_token,
                       container, objectname, 7 * 24 * 3600)

    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    prefixes = prefix_list(prefix)

    return render_to_response('tempurl.html',
                              {'url': url,
                               'account': storage_url.split('/')[-1],
                               'container': container,
                               'prefix': prefix,
                               'prefixes': prefixes,
                               'objectname': objectname,
                               'session': request.session,
                               },
                              context_instance=RequestContext(request))


def create_pseudofolder(request, container, prefix=None):
    """ Creates a pseudofolder (empty object of type application/directory) """
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = PseudoFolderForm(request.POST)
    if form.is_valid():
        foldername = request.POST.get('foldername', None)
        if prefix:
            foldername = prefix + '/' + foldername
        foldername = os.path.normpath(foldername)
        foldername = foldername.strip('/')
        foldername += '/'

        content_type = 'application/directory'
        obj = None

        try:
            client.put_object(storage_url, auth_token,
                              container, foldername, obj,
                              content_type=content_type)
            messages.add_message(request, messages.INFO,
                                 _("Pseudofolder created."))
        except client.ClientException:
            messages.add_message(request, messages.ERROR, _("Access denied."))

        if prefix:
            return redirect(objectview, container=container, prefix=prefix)
        return redirect(objectview, container=container)

    return render_to_response('create_pseudofolder.html', {
                              'container': container,
                              'prefix': prefix,
                              }, context_instance=RequestContext(request))


def get_acls(storage_url, auth_token, container):
    """ Returns ACLs of given container. """
    cont = client.head_container(storage_url, auth_token, container)
    readers = cont.get('x-container-read', '')
    writers = cont.get('x-container-write', '')
    return (readers, writers)


def remove_duplicates_from_acl(acls):
    """ Removes possible duplicates from a comma-separated list. """
    entries = acls.split(',')
    cleaned_entries = list(set(entries))
    acls = ','.join(cleaned_entries)
    return acls


def edit_acl(request, container):
    """ Edit ACLs on given container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    if request.method == 'POST':
        form = AddACLForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']

            try:
                (readers, writers) = get_acls(storage_url,
                    auth_token, container)
            except KeyError:
                return redirect(logout)

            readers = remove_duplicates_from_acl(readers)
            writers = remove_duplicates_from_acl(writers)

            if form.cleaned_data['read']:
                readers += ",%s" % username

            if form.cleaned_data['write']:
                writers += ",%s" % username

            headers = {'X-Container-Read': readers,
                       'X-Container-Write': writers}
            try:
                client.post_container(storage_url,
                    auth_token, container, headers)
                message = "ACLs updated."
                messages.add_message(request, messages.INFO, message)
            except client.ClientException:
                message = "ACL update failed"
                messages.add_message(request, messages.ERROR, message)

    if request.method == 'GET':
        delete = request.GET.get('delete', None)
        if delete:
            users = delete.split(',')

            (readers, writers) = get_acls(storage_url, auth_token, container)

            new_readers = ""
            for element in readers.split(','):
                if element not in users:
                    new_readers += element
                    new_readers += ","

            new_writers = ""
            for element in writers.split(','):
                if element not in users:
                    new_writers += element
                    new_writers += ","

            headers = {'X-Container-Read': new_readers,
                       'X-Container-Write': new_writers}
            try:
                client.post_container(storage_url, auth_token,
                                      container, headers)
                message = "ACL removed."
                messages.add_message(request, messages.INFO, message)
            except client.ClientException:
                message = "ACL update failed."
                messages.add_message(request, messages.ERROR, message)

    (readers, writers) = get_acls(storage_url, auth_token, container)

    acls = {}

    if readers != "":
        readers = remove_duplicates_from_acl(readers)
        for entry in readers.split(','):
            acls[entry] = {}
            acls[entry]['read'] = True
            acls[entry]['write'] = False

    if writers != "":
        writers = remove_duplicates_from_acl(writers)
        for entry in writers.split(','):
            if entry not in acls:
                acls[entry] = {}
                acls[entry]['read'] = False
            acls[entry]['write'] = True

    public = False
    if acls.get('.r:*', False) and acls.get('.rlistings', False):
        public = True

    if request.is_secure():
        base_url = "https://%s" % request.get_host()
    else:
        base_url = "http://%s" % request.get_host()

    return render_to_response('edit_acl.html', {
        'container': container,
        'account': storage_url.split('/')[-1],
        'session': request.session,
        'acls': acls,
        'public': public,
        'base_url': base_url,
    }, context_instance=RequestContext(request))

@require_POST
def upload(request):
    file = upload_receive( request )
    container = request.session.get('container')
    prefix = request.session.get('prefix')    
    instance = Photo(file = file)
    
    if prefix:
        instance.path = os.path.join(container,prefix)
    else:
        instance.path = os.path.join(container)
    
    instance.save()

    basename = os.path.basename( instance.file.path )
    
    file_dict = {
        'name' : basename,
        'size' : file.size,        
        'url': settings.MEDIA_URL + basename,
        'thumbnailUrl': settings.MEDIA_URL + basename,
        'deleteUrl': reverse('jfu_delete', kwargs = { 'pk': instance.pk }),
        'deleteType': 'POST',
    }

    return UploadResponse( request, file_dict )

@require_POST
def upload_delete( request, pk ):
    success = True
    try:
        instance = Photo.objects.get( pk = pk )
        os.unlink( instance.file.path )
        instance.delete()
    except Photo.DoesNotExist:
        success = False

    return JFUResponse( request, success )
