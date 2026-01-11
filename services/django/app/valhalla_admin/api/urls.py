from django.urls import path
from .views import StatusView, BuildTaskListView, BuildTaskStatusView
from .valhalla_proxy import ValhallaProxyView

urlpatterns = [
	path("status/", StatusView.as_view()),
	path("build-tasks/", BuildTaskListView.as_view()),
	path("build-tasks/<int:task_id>/status", BuildTaskStatusView.as_view()),
    # Proxy catch-all pour Valhalla (doit être en dernier)
    # /valhalla/<alias>/api/<path>
    path('<path:path>', ValhallaProxyView.as_view()),
]
