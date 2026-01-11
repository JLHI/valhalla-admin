from django.urls import path
from .views import StatusView, BuildTaskListView, BuildTaskStatusView

urlpatterns = [
	path("status/", StatusView.as_view()),
	path("build-tasks/", BuildTaskListView.as_view()),
	path("build-tasks/<int:task_id>/status", BuildTaskStatusView.as_view()),
]
