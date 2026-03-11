from celery import Celery


celery_app = Celery(__name__)


def init_celery(app) -> Celery:
    celery_app.conf.update(app.config["CELERY"])

    class FlaskTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = FlaskTask
    return celery_app
