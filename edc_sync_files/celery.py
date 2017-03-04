from __future__ import absolute_import, unicode_literals

import os
from celery import Celery

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edc_sync_files.settings')

app = Celery('edc_sync_files')
app.conf.broker_url = 'redis://localhost:6379/0'
app.conf.timezone = 'Africa/Gaborone'
app.conf.broker_transport_options = {'visibility_timeout': 30}

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))