from core.config import settings

broker_url = settings.broker_url
result_backend = settings.result_backend

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# track task state so we can query it via status route
task_track_started = True

# optional: result expiry
result_expires = 60 * 60 * 24  # 24 hours