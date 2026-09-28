"""Local operator provisioning; password and token cryptography remain Django-owned."""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import connection
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from pokemon_hunter.inventory import OWNER_ID

from . import transactions as transaction
from .store import rows


class InviteToken(PasswordResetTokenGenerator):
    key_salt = "dex.b1.invitation"


invite_token = InviteToken()
recovery_token = PasswordResetTokenGenerator()


@transaction.atomic
def bootstrap(password):
    User = get_user_model()
    owners = rows("SELECT * FROM users WHERE id=%s", [OWNER_ID])
    if owners and owners[0]["auth_subject"]:
        user = User.objects.get(pk=owners[0]["auth_subject"])
        if not user.is_active or owners[0]["state"] != "active":
            raise ValueError("Owner revoked; bootstrap cannot reactivate it")
        return user  # Never reset credentials or rebind on repeat.
    if User.objects.exists() or rows("SELECT id FROM users WHERE id<>%s", [OWNER_ID]):
        raise ValueError("Owner must be provisioned first; refusing identity adoption")
    user = User(username="admin")
    validate_password(password, user)
    user.set_password(password)
    user.save()
    with connection.cursor() as c:
        c.execute(
            "INSERT INTO users VALUES(%s,NULL,'admin','owner','unprovisioned') ON CONFLICT DO NOTHING",
            [OWNER_ID],
        )
        c.execute(
            "UPDATE users SET auth_subject=%s,state='active' WHERE id=%s AND auth_subject IS NULL",
            [str(user.pk), OWNER_ID],
        )
    return user


@transaction.atomic
def invite(username):
    if not rows(
        "SELECT id FROM users WHERE id=%s AND auth_subject IS NOT NULL AND state='active'", [OWNER_ID]
    ):
        raise ValueError("Provision the owner first")
    existing = get_user_model().objects.filter(username=username).first()
    if existing:
        mapping = rows("SELECT state,role FROM users WHERE auth_subject=%s", [str(existing.pk)])
        if existing.is_active and mapping and mapping[0] == {"state": "invited", "role": "member"}:
            return existing  # Reissue an expired invitation without creating another identity.
        raise ValueError("Account already exists and is not awaiting invitation redemption")
    user = get_user_model()(username=username)
    user.full_clean(exclude=["password"])
    user.set_unusable_password()
    user.save()
    with connection.cursor() as c:
        c.execute(
            "INSERT INTO users VALUES(%s,%s,%s,'member','invited')",
            [str(uuid.uuid4()), str(user.pk), username],
        )
    return user


@transaction.atomic
def issue_link(user, kind):
    if kind not in {"invite", "recovery"}:
        raise ValueError("Unsupported link purpose")
    user = get_user_model().objects.get(pk=user.pk)
    mapping = rows("SELECT state FROM users WHERE auth_subject=%s", [str(user.pk)])
    if (
        not user.is_active
        or not mapping
        or mapping[0]["state"] != ("invited" if kind == "invite" else "active")
    ):
        raise ValueError("Account state does not permit this link")
    # Supported password mutation invalidates previous links AND all old sessions.
    user.set_unusable_password()
    user.save(update_fields=["password"])
    generator = invite_token if kind == "invite" else recovery_token
    from django.conf import settings

    path = f"{kind}/{urlsafe_base64_encode(force_bytes(user.pk))}/{generator.make_token(user)}"
    return "/access/#" + path if getattr(settings, "STAGING", False) else "/" + path + "/"


@transaction.atomic
def revoke(user):
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=["is_active", "password"])
    with connection.cursor() as c:
        c.execute("UPDATE users SET state='revoked' WHERE auth_subject=%s", [str(user.pk)])
