import sys
import os

# Ensure the app directory is always in the path because it can't find shared
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery import Celery

celery = Celery("celery_app")
celery.config_from_object("celery_config")
celery.autodiscover_tasks(["modules.ingestion", "modules.document"])