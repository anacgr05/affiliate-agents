from celery_app import celery_app

# Simulated event dispatcher
celery_app.send_task("backend.worker.generate_image_task", kwargs={"post_id": 1, "prompt": "Capa do post sobre inovacao"})
print("Dispatched Epic 03 trigger.")
