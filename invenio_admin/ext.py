# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio-Admin Flask extension."""

from __future__ import absolute_import, print_function

import pkg_resources

from flask_admin import Admin, AdminIndexView
from invenio_db import db

from . import config
from .permissions import admin_permission_factory
from .views import protected_adminview_factory


class _AdminState(object):
    """State for Invenio-Admin."""

    def __init__(self, app, admin, permission_factory, view_class_factory):
        """Initialize state.

        :param app: The Flask application.
        :param admin: The Flask-Admin application.
        :param permission_factory: The permission factory to restrict access.
        :param view_class_factory: The view class factory to initialize them.
        """
        # Create admin instance.
        self.app = app
        self.admin = admin
        self.permission_factory = permission_factory
        self.view_class_factory = view_class_factory

    def register_view(self, view_class, model_class, session=None, **kwargs):
        """Register an admin view on this admin instance.

        :param view_class: The view class name passed to the view factory.
        :param model_class: The model class name.
        :param session: The session handler. If not specified, ``db.session``
            will be used. (Default: ``None``)
        :param kwargs: Passed to the ``view_class`` returned from the
            ``view_class_factory``.
        """
        view_class = self.view_class_factory(view_class)
        self.admin.add_view(
            view_class(model_class, session or db.session, **kwargs))

    def load_entry_point_group(self, entry_point_group):
        """Load administration interface from entry point group.

        :param str entry_point_group: Name of the entry point group.
        """
        for ep in pkg_resources.iter_entry_points(group=entry_point_group):
            admin_ep = dict(ep.load())
            assert 'model' in admin_ep, \
                "Admin's entrypoint dictionary must define the 'model'"
            assert 'modelview' in admin_ep, \
                "Admin's entrypoint dictionary must define the 'modelview'"

            self.register_view(
                admin_ep.pop('modelview'),
                admin_ep.pop('model'),
                **admin_ep)


class InvenioAdmin(object):
    """Invenio-Admin extension."""

    def __init__(self, app=None, **kwargs):
        """Invenio-Admin extension initialization.

        :param app: The Flask application. (Default: ``None``)
        :param kwargs: Passed to :meth:`init_app`.
        """
        if app:
            self._state = self.init_app(app, **kwargs)

    def init_app(self,
                 app,
                 entry_point_group='invenio_admin.views',
                 permission_factory=admin_permission_factory,
                 view_class_factory=protected_adminview_factory,
                 index_view_class=AdminIndexView):
        """Flask application initialization.

        :param app: The Flask application.
        :param entry_point_group: Name of entry point group to load
            views/models from. (Default: ``'invenio_admin.views'``)
        :param permission_factory: Default permission factory to use when
            protecting an admin view. (Default:
            :func:`~.permissions.admin_permission_factory`)
        :param view_class_factory: Factory for creating admin view classes on
            the fly. Used to protect admin views with authentication and
            authorization. (Default:
            :func:`~.views.protected_adminview_factory`)
        :param index_view_class: Specify administrative interface index page.
            (Default: :class:`flask_admin.base.AdminIndexView`)
        :param kwargs: Passed to :class:`flask_admin.base.Admin`.
        :returns: Extension state.
        """
        self.init_config(app)

        # Create administration app.
        admin = Admin(
            app,
            name=app.config['ADMIN_APPNAME'],
            template_mode=app.config['ADMIN_TEMPLATE_MODE'],
            index_view=view_class_factory(index_view_class)(),
        )

        @app.before_first_request
        def lazy_base_template():
            """Initialize admin base template lazily."""
            base_template = app.config.get('ADMIN_BASE_TEMPLATE')
            if base_template:
                admin.base_template = base_template

        # Create admin state
        state = _AdminState(app, admin, permission_factory, view_class_factory)
        if entry_point_group:
            state.load_entry_point_group(entry_point_group)

        app.extensions['invenio-admin'] = state
        return state

    @staticmethod
    def init_config(app):
        """Initialize configuration.

        :param app: The Flask application.
        """
        # Set default configuration
        for k in dir(config):
            if k == 'ADMIN_BASE_TEMPLATE':
                try:
                    pkg_resources.get_distribution('invenio-theme')
                    continue
                except pkg_resources.DistributionNotFound:
                    pass
            if k.startswith('ADMIN_'):
                app.config.setdefault(k, getattr(config, k))

    def __getattr__(self, name):
        """Proxy to state object.

        :param name: Attribute name of the state.
        """
        return getattr(self._state, name, None)
