"""
src/api/semp.py — Solace SEMP v2 Config API (full CRUD)
=========================================================
Base URL: https://<broker>:943/SEMP/v2/config/msgVpns/{vpn}
Auth:     HTTP Basic (admin username + password from service details)

──────────────────────────────────────────────────────────────────────────
 OBJECT              METHOD  ENDPOINT (relative to /msgVpns/{vpn})
──────────────────────────────────────────────────────────────────────────
 [A] CREDENTIALS
 ClientProfile        GET    /clientProfiles
                      POST   /clientProfiles
                      GET    /clientProfiles/{name}
                      PATCH  /clientProfiles/{name}
                      DELETE /clientProfiles/{name}
 AclProfile           GET    /aclProfiles
                      POST   /aclProfiles
                      GET    /aclProfiles/{name}
                      PATCH  /aclProfiles/{name}
                      DELETE /aclProfiles/{name}
 AclProfile PubExc    POST   /aclProfiles/{name}/publishTopicExceptions
                      DELETE /aclProfiles/{name}/publishTopicExceptions/{syntax},{topic}
 AclProfile SubExc    POST   /aclProfiles/{name}/subscribeTopicExceptions
                      DELETE /aclProfiles/{name}/subscribeTopicExceptions/{syntax},{topic}
 ClientUsername        GET    /clientUsernames
                      POST   /clientUsernames
                      GET    /clientUsernames/{name}
                      PATCH  /clientUsernames/{name}
                      DELETE /clientUsernames/{name}
──────────────────────────────────────────────────────────────────────────
 [B] MESSAGING
 Queue                GET    /queues
                      POST   /queues
                      GET    /queues/{name}
                      PATCH  /queues/{name}
                      DELETE /queues/{name}
 QueueSubscription    GET    /queues/{name}/subscriptions
                      POST   /queues/{name}/subscriptions
                      DELETE /queues/{name}/subscriptions/{topic}
──────────────────────────────────────────────────────────────────────────
 [C] REST DELIVERY POINT
 RDP                  GET    /restDeliveryPoints
                      POST   /restDeliveryPoints
                      GET    /restDeliveryPoints/{name}
                      PATCH  /restDeliveryPoints/{name}
                      DELETE /restDeliveryPoints/{name}
 RestConsumer         GET    /restDeliveryPoints/{rdp}/restConsumers
                      POST   /restDeliveryPoints/{rdp}/restConsumers
                      GET    /restDeliveryPoints/{rdp}/restConsumers/{name}
                      PATCH  /restDeliveryPoints/{rdp}/restConsumers/{name}
                      DELETE /restDeliveryPoints/{rdp}/restConsumers/{name}
 QueueBinding         GET    /restDeliveryPoints/{rdp}/queueBindings
                      POST   /restDeliveryPoints/{rdp}/queueBindings
                      DELETE /restDeliveryPoints/{rdp}/queueBindings/{queue}
──────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
from typing import Optional
from client import SolaceClient, SolaceError

logger = logging.getLogger(__name__)


def _list(r): return r.get("data", [])
def _data(r): return r.get("data", r)


def _already_exists(exc: SolaceError) -> bool:
    """Return True when SEMP says the object already exists (code 10 / ALREADY_EXISTS)."""
    body = exc.body if isinstance(exc.body, dict) else {}
    err  = body.get("meta", {}).get("error", {})
    return (err.get("code") == 10
            or "ALREADY_EXISTS" in err.get("status", "")
            or "already exists" in err.get("description", "").lower())


class SempAPI:
    """
    Full SEMP v2 config API wrapper.

    All paths are relative to /msgVpns/{vpn_name} on the broker.
    """

    def __init__(self, client: SolaceClient, vpn_name: str):
        self.c   = client
        self.vpn = vpn_name

    def _p(self, suffix: str) -> str:
        return f"/msgVpns/{self.vpn}{suffix}"

    def _url(self, suffix: str) -> str:
        return self._p(suffix)

    # ══════════════════════════════════════════════════════════════════════
    # A. CREDENTIALS
    # ══════════════════════════════════════════════════════════════════════

    # ── Client Profile ────────────────────────────────────────────────────
    def list_client_profiles(self) -> list[dict]:
        return _list(self.c.semp_get(self._p("/clientProfiles")))

    def get_client_profile(self, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/clientProfiles/{name}")))

    def create_client_profile(self, name: str, **overrides) -> dict:
        payload = {
            "clientProfileName":                  name,
            "msgVpnName":                         self.vpn,
            "allowBridgeConnectionsEnabled":      False,
            "allowGuaranteedMsgSendEnabled":      True,
            "allowGuaranteedMsgReceiveEnabled":   True,
            "allowTransactedSessionsEnabled":     True,
            **overrides,
        }
        logger.info("Creating Client Profile '%s'", name)
        try:
            d = _data(self.c.semp_post(self._p("/clientProfiles"), payload))
            logger.info("  ✓ Client Profile created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ Client Profile '%s' already exists — skipping", name)
                return self.get_client_profile(name)
            raise

    def update_client_profile(self, name: str, **fields) -> dict:
        return _data(self.c.semp_patch(self._p(f"/clientProfiles/{name}"),
                                       {"msgVpnName": self.vpn, **fields}))

    def delete_client_profile(self, name: str) -> None:
        self.c.semp_delete(self._p(f"/clientProfiles/{name}"))
        logger.info("  ✓ Deleted client profile '%s'", name)

    # ── ACL Profile ───────────────────────────────────────────────────────
    def list_acl_profiles(self) -> list[dict]:
        return _list(self.c.semp_get(self._p("/aclProfiles")))

    def get_acl_profile(self, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/aclProfiles/{name}")))

    def create_acl_profile(self, name: str,
                            client_connect: str = "allow",
                            publish_default: str = "disallow",
                            subscribe_default: str = "disallow") -> dict:
        """default_action: 'allow' | 'disallow'"""
        payload = {
            "aclProfileName":               name,
            "msgVpnName":                   self.vpn,
            "clientConnectDefaultAction":    client_connect,
            "publishTopicDefaultAction":     publish_default,
            "subscribeTopicDefaultAction":   subscribe_default,
        }
        logger.info("Creating ACL Profile '%s'", name)
        try:
            d = _data(self.c.semp_post(self._p("/aclProfiles"), payload))
            logger.info("  ✓ ACL Profile created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ ACL Profile '%s' already exists — skipping", name)
                return self.get_acl_profile(name)
            raise

    def delete_acl_profile(self, name: str) -> None:
        self.c.semp_delete(self._p(f"/aclProfiles/{name}"))

    def list_publish_exceptions(self, acl: str) -> list[dict]:
        """GET /aclProfiles/{acl}/publishTopicExceptions"""
        return _list(self.c.semp_get(self._p(f"/aclProfiles/{acl}/publishTopicExceptions")))

    def list_subscribe_exceptions(self, acl: str) -> list[dict]:
        """GET /aclProfiles/{acl}/subscribeTopicExceptions"""
        return _list(self.c.semp_get(self._p(f"/aclProfiles/{acl}/subscribeTopicExceptions")))

    def add_publish_exception(self, acl: str, topic: str,
                               syntax: str = "smf") -> dict:
        """POST /aclProfiles/{acl}/publishTopicExceptions  (idempotent — skips duplicates)."""
        try:
            return _data(self.c.semp_post(
                self._p(f"/aclProfiles/{acl}/publishTopicExceptions"),
                {"publishTopicException": topic,
                 "publishTopicExceptionSyntax": syntax,
                 "aclProfileName": acl,
                 "msgVpnName": self.vpn}
            ))
        except SolaceError as exc:
            if _already_exists(exc):
                logger.debug("  Publish exception '%s' already exists — skipping", topic)
                return {}
            raise

    def remove_publish_exception(self, acl: str, topic: str,
                                  syntax: str = "smf") -> None:
        encoded = topic.replace("/", "%2F").replace("*", "%2A").replace(">", "%3E")
        self.c.semp_delete(
            self._p(f"/aclProfiles/{acl}/publishTopicExceptions/{syntax},{encoded}")
        )

    def add_subscribe_exception(self, acl: str, topic: str,
                                 syntax: str = "smf") -> dict:
        """POST /aclProfiles/{acl}/subscribeTopicExceptions  (idempotent — skips duplicates)."""
        try:
            return _data(self.c.semp_post(
                self._p(f"/aclProfiles/{acl}/subscribeTopicExceptions"),
                {"subscribeTopicException": topic,
                 "subscribeTopicExceptionSyntax": syntax,
                 "aclProfileName": acl,
                 "msgVpnName": self.vpn}
            ))
        except SolaceError as exc:
            if _already_exists(exc):
                logger.debug("  Subscribe exception '%s' already exists — skipping", topic)
                return {}
            raise

    def remove_subscribe_exception(self, acl: str, topic: str,
                                    syntax: str = "smf") -> None:
        encoded = topic.replace("/", "%2F").replace("*", "%2A").replace(">", "%3E")
        self.c.semp_delete(
            self._p(f"/aclProfiles/{acl}/subscribeTopicExceptions/{syntax},{encoded}")
        )

    # ── Client Username ───────────────────────────────────────────────────
    def list_client_usernames(self) -> list[dict]:
        return _list(self.c.semp_get(self._p("/clientUsernames")))

    def get_client_username(self, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/clientUsernames/{name}")))

    def create_client_username(self, name: str, password: str,
                                client_profile: str, acl_profile: str,
                                enabled: bool = True) -> dict:
        payload = {
            "clientUsername":    name,
            "password":          password,
            "clientProfileName": client_profile,
            "aclProfileName":    acl_profile,
            "enabled":           enabled,
            "msgVpnName":        self.vpn,
        }
        logger.info("Creating Client Username '%s'", name)
        try:
            d = _data(self.c.semp_post(self._p("/clientUsernames"), payload))
            logger.info("  ✓ Client Username created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ Client Username '%s' already exists — skipping", name)
                return self.get_client_username(name)
            raise

    def update_client_username(self, name: str, **fields) -> dict:
        return _data(self.c.semp_patch(self._p(f"/clientUsernames/{name}"),
                                       {"msgVpnName": self.vpn, **fields}))

    def delete_client_username(self, name: str) -> None:
        self.c.semp_delete(self._p(f"/clientUsernames/{name}"))

    # ══════════════════════════════════════════════════════════════════════
    # B. MESSAGING OBJECTS
    # ══════════════════════════════════════════════════════════════════════

    # ── Queue ─────────────────────────────────────────────────────────────
    def list_queues(self) -> list[dict]:
        return _list(self.c.semp_get(self._p("/queues")))

    def get_queue(self, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/queues/{name}")))

    def create_queue(self, name: str,
                     owner: str = None,
                     access_type: str = "non-exclusive",
                     max_msg_size: int = 10_000_000,
                     max_spool_mb: int = 1500,
                     egress: bool = True,
                     ingress: bool = True,
                     **overrides) -> dict:
        """
        access_type: 'exclusive' | 'non-exclusive'
        max_msg_size: bytes (capped at broker system max — usually 10_000_000)
        max_spool_mb: megabytes
        """
        payload = {
            "queueName":       name,
            "msgVpnName":      self.vpn,
            "accessType":      access_type,
            "egressEnabled":   egress,
            "ingressEnabled":  ingress,
            "maxMsgSize":      max_msg_size,
            "maxMsgSpoolUsage": max_spool_mb,
            "permission":      "consume",
            **overrides,
        }
        if owner:
            payload["owner"] = owner
        logger.info("Creating Queue '%s' (type=%s)", name, access_type)
        try:
            d = _data(self.c.semp_post(self._p("/queues"), payload))
            logger.info("  ✓ Queue created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ Queue '%s' already exists — skipping", name)
                return self.get_queue(name)
            raise

    def update_queue(self, name: str, **fields) -> dict:
        return _data(self.c.semp_patch(self._p(f"/queues/{name}"),
                                       {"msgVpnName": self.vpn, **fields}))

    def delete_queue(self, name: str) -> None:
        self.c.semp_delete(self._p(f"/queues/{name}"))
        logger.info("  ✓ Deleted queue '%s'", name)

    # Queue Subscriptions
    def list_queue_subscriptions(self, queue: str) -> list[dict]:
        return _list(self.c.semp_get(self._p(f"/queues/{queue}/subscriptions")))

    def add_queue_subscription(self, queue: str, topic: str) -> dict:
        """POST /queues/{queue}/subscriptions  (idempotent — skips duplicates)."""
        logger.info("  Adding subscription '%s' → queue '%s'", topic, queue)
        try:
            d = _data(self.c.semp_post(
                self._p(f"/queues/{queue}/subscriptions"),
                {"subscriptionTopic": topic, "queueName": queue, "msgVpnName": self.vpn}
            ))
            logger.info("  ✓ Subscription added")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ Subscription '%s' already exists — skipping", topic)
                return {}
            raise

    def remove_queue_subscription(self, queue: str, topic: str) -> None:
        enc = topic.replace("/", "%2F").replace("*", "%2A").replace(">", "%3E")
        self.c.semp_delete(self._p(f"/queues/{queue}/subscriptions/{enc}"))

    # ══════════════════════════════════════════════════════════════════════
    # C. REST DELIVERY POINTS
    # ══════════════════════════════════════════════════════════════════════
    def list_rdps(self) -> list[dict]:
        return _list(self.c.semp_get(self._p("/restDeliveryPoints")))

    def get_rdp(self, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/restDeliveryPoints/{name}")))

    def create_rdp(self, name: str, client_profile: str = "default",
                   enabled: bool = True) -> dict:
        payload = {
            "restDeliveryPointName": name,
            "msgVpnName":            self.vpn,
            "clientProfileName":     client_profile,
            "enabled":               enabled,
        }
        logger.info("Creating RDP '%s'", name)
        try:
            d = _data(self.c.semp_post(self._p("/restDeliveryPoints"), payload))
            logger.info("  ✓ RDP created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ RDP '%s' already exists — skipping", name)
                return self.get_rdp(name)
            raise

    def delete_rdp(self, name: str) -> None:
        self.c.semp_delete(self._p(f"/restDeliveryPoints/{name}"))

    # REST Consumers
    def list_rest_consumers(self, rdp: str) -> list[dict]:
        return _list(self.c.semp_get(self._p(f"/restDeliveryPoints/{rdp}/restConsumers")))

    def get_rest_consumer(self, rdp: str, name: str) -> dict:
        return _data(self.c.semp_get(self._p(f"/restDeliveryPoints/{rdp}/restConsumers/{name}")))

    def create_rest_consumer(self, rdp: str, name: str,
                              host: str, port: int = 443,
                              tls: bool = True,
                              http_method: str = "post",
                              auth_scheme: str = "none",
                              **overrides) -> dict:
        """
        http_method:  'post' | 'put'
        auth_scheme:  'none' | 'http-basic' | 'http-header' | 'oauth-client-credentials'
        """
        payload = {
            "restConsumerName":      name,
            "restDeliveryPointName": rdp,
            "msgVpnName":            self.vpn,
            "remoteHost":            host,
            "remotePort":            port,
            "tlsEnabled":            tls,
            "httpMethod":            http_method,
            "authenticationScheme":  auth_scheme,
            "enabled":               True,
            **overrides,
        }
        logger.info("Creating REST Consumer '%s' → %s:%s", name, host, port)
        try:
            d = _data(self.c.semp_post(
                self._p(f"/restDeliveryPoints/{rdp}/restConsumers"), payload
            ))
            logger.info("  ✓ REST Consumer created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ REST Consumer '%s' already exists — skipping", name)
                return self.get_rest_consumer(rdp, name)
            raise

    def update_rest_consumer(self, rdp: str, name: str, **fields) -> dict:
        return _data(self.c.semp_patch(
            self._p(f"/restDeliveryPoints/{rdp}/restConsumers/{name}"),
            {"msgVpnName": self.vpn, "restDeliveryPointName": rdp, **fields}
        ))

    def delete_rest_consumer(self, rdp: str, name: str) -> None:
        self.c.semp_delete(self._p(f"/restDeliveryPoints/{rdp}/restConsumers/{name}"))

    # Queue Bindings
    def list_queue_bindings(self, rdp: str) -> list[dict]:
        return _list(self.c.semp_get(self._p(f"/restDeliveryPoints/{rdp}/queueBindings")))

    def bind_queue_to_rdp(self, rdp: str, queue: str,
                           post_target: str = "/") -> dict:
        """POST /restDeliveryPoints/{rdp}/queueBindings — bind queue → RDP."""
        payload = {
            "queueBindingName":      queue,
            "postRequestTarget":     post_target,
            "restDeliveryPointName": rdp,
            "msgVpnName":            self.vpn,
        }
        logger.info("Binding queue '%s' → RDP '%s'  (target=%s)", queue, rdp, post_target)
        try:
            d = _data(self.c.semp_post(
                self._p(f"/restDeliveryPoints/{rdp}/queueBindings"), payload
            ))
            logger.info("  ✓ Queue binding created")
            return d
        except SolaceError as exc:
            if _already_exists(exc):
                logger.info("  ↩ Queue binding '%s' already exists — skipping", queue)
                return {}
            raise

    def unbind_queue_from_rdp(self, rdp: str, queue: str) -> None:
        self.c.semp_delete(self._p(f"/restDeliveryPoints/{rdp}/queueBindings/{queue}"))
