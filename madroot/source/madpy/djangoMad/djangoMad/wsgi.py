# -*- coding: utf-8 -*-

"""
WSGI config for djangoMad project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/
"""

import os, os.path
import madrigal.metadata

madDB = madrigal.metadata.MadrigalDB()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoMad.settings_production")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
