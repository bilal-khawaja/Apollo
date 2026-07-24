from celery import Celery

celery_app = Celery(
    'worker_setup', 
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include = ['feat.resource_checker']
    )

celery_app.conf.beat_schedule = {
    "process_low_stack_products" : {
    "task": "feat.resource_checker.process_low_stock_items",
    "schedule": 1800.0
    },
}

celery_app.conf.timezone = 'UTC'