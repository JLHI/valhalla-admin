from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from django.shortcuts import get_object_or_404

from valhalla_admin.graph.models import BuildTask


class BuildTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuildTask
        fields = [
            "id", "name", "status", "is_ready", "is_serving",
            "serve_port", "created_at", "started_at", "finished_at"
        ]


class StatusView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class BuildTaskListView(APIView):
    """List recent BuildTasks with lightweight fields."""
    def get(self, request):
        qs = BuildTask.objects.order_by("-created_at")[:50]
        data = BuildTaskSerializer(qs, many=True).data
        return Response({"items": data, "count": len(data)})


class BuildTaskStatusView(APIView):
    """Return detailed status for a single BuildTask, including logs preview."""
    def get(self, request, task_id: int):
        bt = get_object_or_404(BuildTask, id=task_id)
        logs_text = bt.logs or ""
        lines = logs_text.splitlines()
        total = len(lines)
        head_count = 40
        tail_count = 40
        head = lines[:head_count]
        tail = lines[-tail_count:] if total > tail_count else lines
        if total > head_count + tail_count:
            preview_lines = head + ["… (logs tronqués) …"] + tail
        else:
            preview_lines = lines
        preview_text = "\n".join(preview_lines)
        return Response({
            "id": bt.id,
            "name": bt.name,
            "status": bt.status,
            "ready": bt.is_ready,
            "serving": bt.is_serving,
            "serve_port": bt.serve_port,
            "logs_preview": preview_text,
            "logs_total_lines": total,
        })