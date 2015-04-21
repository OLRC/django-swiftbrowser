django-swiftbrowser
===================

This is a fork of [cschwede / django-swiftbrowser](https://github.com/cschwede/django-swiftbrowser) that adds [django-jfu](https://github.com/Alem/django-jfu) as the file upload form.

Quick Install
-------------

1) Install swiftbrowser:

    git clone git://github.com/bkawula/django-swiftbrowser.git
    cd django-swiftbrowser
    sudo python setup.py install

   Optional: run tests

    python runtests.py

2.1) Create a new Django project:

    django-admin.py startproject myproj
    cd myproj
    cp ../example/settings.py myproj/settings.py
	mkdir myproj/database

2.2) For development make symlink to the swiftbrowser folder

	ln -s ../swiftbrowser swiftbrowser

3) Adopt myproj/settings.py to your needs, especially settings for Swift.

4) Update myproj/urls.py and include swiftbrowser.urls and add it to the url patterns.

    import swiftbrowser.urls

    urlpatterns = patterns('',
        url(r'^', include(swiftbrowser.urls)),
    )

5) Sync Database

	python manage.py syncdb

6) Collect static files:

    python manage.py collectstatic

7) Run development server:

    python manage.py runserver

   *Important*: Either use 'python manage.py runserver --insecure' or set DEBUG = True in myproj/settings.py if you want to use the
   local development server. Don't use these settings in production!
