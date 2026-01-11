from celery import Celery
from celery import signals
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE","valhalla_admin.settings")
app = Celery("valhalla_admin")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@signals.task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, einfo=None, **others):
	"""Marque la BuildTask en erreur quand une tâche Valhalla échoue (y compris WorkerLostError)."""
	try:
		task_name = getattr(sender, "name", "")
		if task_name not in (
			"valhalla_admin.graph.tasks.start_valhalla_build",
			"valhalla_admin.graph.tasks.run_valhalla_build",
		):
			return

		build_task_id = None
		if args:
			build_task_id = args[0]
		elif kwargs and "task_id" in kwargs:
			build_task_id = kwargs.get("task_id")

		if not build_task_id:
			return

		from django.db import close_old_connections
		close_old_connections()
		from valhalla_admin.graph.models import BuildTask

		bt = BuildTask.objects.filter(id=build_task_id).first()
		if not bt:
			return

		bt.status = "error"
		
		# Capturer les infos OOM-killer depuis dmesg si possible
		oom_info = ""
		try:
			import subprocess
			dmesg = subprocess.run(
				["docker", "exec", "valhallaDjango", "dmesg", "-T"],
				capture_output=True,
				text=True,
				timeout=3
			)
			if "oom" in dmesg.stdout.lower() or "killed process" in dmesg.stdout.lower():
				oom_lines = [line for line in dmesg.stdout.split("\n") if "oom" in line.lower() or "killed" in line.lower()]
				if oom_lines:
					oom_info = "\n\n🔴 OOM DÉTECTÉ:\n" + "\n".join(oom_lines[-10:])
		except Exception:
			pass
		
		bt.add_log(f"❌ Tâche interrompue ({type(exception).__name__}): {exception}{oom_info}")
		bt.save(update_fields=["status"])
	except Exception:
		# Ne jamais bloquer le worker sur le handler
		return
