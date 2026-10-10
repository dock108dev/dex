"""Private support, erasure and deliberately content-free diagnostics."""

import time
import uuid

from django.contrib.auth import get_user_model, logout
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import store
from . import transactions as transaction
from .collection import execute
from .collection_views import endpoint
from .diagnostics import failure
from .views import actor


@transaction.atomic
def delete_account(who):
    store.verified(who)
    uid = who.user_id
    user = get_user_model().objects.get(pk=who.subject)
    from axes.models import AccessAttempt, AccessFailureLog, AccessLog

    for model in (AccessAttempt, AccessLog, AccessFailureLog):
        model.objects.filter(username=user.username).delete()
    from .pack_research import available

    if available():
        execute("DELETE FROM saved_pack_research WHERE user_id=%s", [uid])
    from .shopping import available as shopping_available

    if shopping_available():
        execute("DELETE FROM saved_shopping_comparisons WHERE user_id=%s", [uid])
    # Keep catalog publication integrity and a non-login, non-identifying spend tombstone.
    # The lifetime global reservation sum must never fall on account deletion.
    for table in (
        "catalog_submissions",
        "scan_photos",
        "beta_feedback",
        "b1_private_resources",
        "collection_operations",
        "collection_goals",
        "collection_generations",
        "private_archives",
        "saved_hunts",
    ):
        execute(f"DELETE FROM {table} WHERE user_id=%s", [uid])
    execute(
        "DELETE FROM import_records WHERE batch_id IN (SELECT id FROM import_batches WHERE user_id=%s)", [uid]
    )
    execute(
        "DELETE FROM migration_issues WHERE batch_id IN (SELECT id FROM import_batches WHERE user_id=%s)",
        [uid],
    )
    execute("DELETE FROM owned_copies WHERE user_id=%s", [uid])
    execute("DELETE FROM binders WHERE user_id=%s", [uid])
    execute("DELETE FROM import_batches WHERE user_id=%s", [uid])
    execute(
        "UPDATE scan_jobs SET state='cancelled',result='{}',selection=NULL,copy_id=NULL,operation_id=NULL,error='',fixture='',version='',model='' WHERE user_id=%s",
        [uid],
    )
    execute("UPDATE users SET state='deleted',auth_subject=NULL,login_name=NULL WHERE id=%s", [uid])
    execute("UPDATE catalog_audit SET actor_id='deleted-account' WHERE actor_id=%s", [uid])
    for session in Session.objects.all().iterator():
        if str(session.get_decoded().get("_auth_user_id")) == str(who.subject):
            session.delete()
    user.delete()


@transaction.atomic
def cleanup():
    from django.utils import timezone

    from . import scans

    scans.cleanup()
    execute("DELETE FROM beta_feedback WHERE created<%s", [time.time() - 30 * 86400])
    Session.objects.filter(expire_date__lt=timezone.now()).delete()
    # Scrub expired unconfirmed evidence without erasing spend history.
    execute(
        "UPDATE scan_jobs SET result='{}',selection=NULL,error='' WHERE operation_id IS NULL AND created<%s",
        [time.time() - 7 * 86400],
    )


def diagnostics():
    return {
        "jobs": store.rows("SELECT state,count(*) AS count FROM scan_jobs GROUP BY state"),
        "recognition": store.rows(
            "SELECT sum(reserved_usd) AS reserved_usd,sum(cost_usd) AS known_cost_usd,avg(latency) AS mean_latency_seconds FROM scan_jobs"
        )[0],
        "worker": store.rows("SELECT value FROM beta_operations WHERE key='worker_heartbeat'"),
        "schema": 5,
    }


@endpoint
@require_GET
def page(request):
    actor(request)
    return render(request, "beta/support.html")


@endpoint
@require_POST
def feedback(request):
    who = actor(request)
    message = request.POST.get("message", "").strip()
    if not message or len(message) > 2000:
        raise ValueError("Enter 1–2000 characters")
    count = store.rows(
        "SELECT count(*) AS n FROM beta_feedback WHERE user_id=%s AND created>%s",
        [who.user_id, time.time() - 86400],
    )[0]["n"]
    if count >= 10:
        raise ValueError("Daily feedback limit reached")
    execute(
        "INSERT INTO beta_feedback VALUES(%s,%s,%s,%s)",
        [str(uuid.uuid4()), who.user_id, message, time.time()],
    )
    return render(request, "beta/support.html", {"notice": "Feedback saved privately. Thank you."})


@endpoint
@require_POST
def erase(request):
    who = actor(request)
    if request.POST.get("confirmation") != "DELETE" or not request.user.check_password(
        request.POST.get("password", "")
    ):
        raise ValueError("Enter DELETE and your current password")
    delete_account(who)
    logout(request)
    return render(
        request,
        "beta/support.html",
        {"notice": "Account and private collection deleted. Backups expire within seven days."},
    )


def health(request):
    try:
        from . import scans

        schema = store.rows("SELECT value FROM beta_operations WHERE key='schema'")
        heartbeat = store.rows("SELECT value FROM beta_operations WHERE key='worker_heartbeat'")
        ready = (
            schema == [{"value": "5"}]
            and bool(heartbeat)
            and time.time() - float(heartbeat[0]["value"]) < 180
        )
        scans.config()
        return JsonResponse({"ready": ready}, status=200 if ready else 503)
    except Exception as exc:
        failure("health_check_failed", exc)
        return JsonResponse({"ready": False}, status=503)
