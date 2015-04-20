import logging
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.babel import Babel
from flaskext.gravatar import Gravatar
from flask.ext.cache import Cache
from flask.ext.mail import Mail
from flask.ext.assets import Environment
import formencode_jinja2
from celery import Celery
from cubes import Workspace
from cubes.extensions import extensions

from openspending import default_settings
from openspending.lib.routing import NamespaceRouteRule
from openspending.lib.routing import FormatConverter, NoDotConverter
from openspending.etl.manager import DataManager

logging.basicConfig(level=logging.DEBUG)

# specific loggers
logging.getLogger('cubes').setLevel(logging.WARNING)
logging.getLogger('markdown').setLevel(logging.WARNING)


db = SQLAlchemy()
babel = Babel()
login_manager = LoginManager()
cache = Cache()
mail = Mail()
assets = Environment()
data_manager = DataManager()


def create_app(**config):
    app = Flask(__name__)
    app.url_rule_class = NamespaceRouteRule
    app.url_map.converters['fmt'] = FormatConverter
    app.url_map.converters['nodot'] = NoDotConverter

    app.config.from_object(default_settings)
    app.config.from_envvar('OPENSPENDING_SETTINGS', silent=True)
    app.config.update(config)

    app.jinja_options['extensions'].extend([
        formencode_jinja2.formfill,
        'jinja2.ext.i18n'
    ])

    db.init_app(app)
    babel.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    assets.init_app(app)
    login_manager.init_app(app)
    data_manager.init_app(app)

    from openspending.model.provider import OpenSpendingStore
    extensions.store.extensions['openspending'] = OpenSpendingStore
    app.cubes_workspace = Workspace()
    app.cubes_workspace.register_default_store('openspending')

    return app


def create_web_app(**config):
    app = create_app(**config)

    from openspending.views import register_views
    register_views(app, babel)

    Gravatar(app, size=200, rating='g',
             default='retro', use_ssl=True)

    return app


def create_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return celery.Task.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery