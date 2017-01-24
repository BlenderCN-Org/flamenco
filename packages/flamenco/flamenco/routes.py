import functools
import logging

from flask import Blueprint, render_template, redirect, url_for

import flask_login

from pillar.web.utils import attach_project_pictures
import pillar.web.subquery
from pillar.web.system_util import pillar_api
import pillarsdk

from flamenco import current_flamenco


blueprint = Blueprint('flamenco', __name__)
log = logging.getLogger(__name__)


@blueprint.route('/')
def index():
    api = pillar_api()

    # TODO: add projections.
    projects = current_flamenco.flamenco_projects()

    for project in projects['_items']:
        attach_project_pictures(project, api)

    projs_with_summaries = [
        (proj, current_flamenco.job_manager.job_status_summary(proj['_id']))
        for proj in projects['_items']
        ]

    return render_template('flamenco/index.html',
                           projs_with_summaries=projs_with_summaries)


def error_project_not_setup_for_flamenco():
    return render_template('flamenco/errors/project_not_setup.html')


def flamenco_project_view(extra_project_projections=None, extension_props=False):
    """Decorator, replaces the first parameter project_url with the actual project.

    Assumes the first parameter to the decorated function is 'project_url'. It then
    looks up that project, checks that it's set up for Flamenco, and passes it to the
    decorated function.

    If not set up for flamenco, uses error_project_not_setup_for_flamenco() to render
    the response.

    :param extra_project_projections: extra projections to use on top of the ones already
        used by this decorator.
    :type extra_project_projections: dict
    :param extension_props: whether extension properties should be included. Includes them
        in the projections, and verifies that they are there.
    :type extension_props: bool
    """

    from . import EXTENSION_NAME

    if callable(extra_project_projections):
        raise TypeError('Use with @flamenco_project_view() <-- note the parentheses')

    projections = {
        '_id': 1,
        'name': 1,
        # We don't need this here, but this way the wrapped function has access
        # to the orignal URL passed to it.
        'url': 1,
    }
    if extra_project_projections:
        projections.update(extra_project_projections)
    if extension_props:
        projections['extension_props.%s' % EXTENSION_NAME] = 1

    def decorator(wrapped):
        @functools.wraps(wrapped)
        def wrapper(project_url, *args, **kwargs):
            if isinstance(project_url, pillarsdk.Resource):
                # This is already a resource, so this call probably is from one
                # view to another. Assume the caller knows what he's doing and
                # just pass everything along.
                return wrapped(project_url, *args, **kwargs)

            api = pillar_api()

            project = pillarsdk.Project.find_by_url(
                project_url,
                {'projection': projections},
                api=api)

            is_flamenco = current_flamenco.is_flamenco_project(
                project, test_extension_props=extension_props)
            if not is_flamenco:
                return error_project_not_setup_for_flamenco()

            if extension_props:
                pprops = project.extension_props.flamenco
                return wrapped(project, pprops, *args, **kwargs)
            return wrapped(project, *args, **kwargs)

        return wrapper

    return decorator


@blueprint.route('/<project_url>')
@flamenco_project_view(extension_props=False)
def project_index(project):
    return redirect(url_for('flamenco.jobs.perproject.index', project_url=project.url))


@blueprint.route('/<project_url>/help')
@flamenco_project_view(extension_props=False)
def help(project):
    return render_template('flamenco/help.html', statuses=[])
