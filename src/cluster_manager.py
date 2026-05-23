"""
Solace Cluster Manager — Runtime Object Automation
===================================================
Uses the Solace Cloud SEMP v2 REST API to create/manage Cluster Management Objects:

  A. User Credentials  → Client Profile, ACL Profile, Client Username
  B. Messaging Objects → Queues + Topic Subscriptions
  C. REST Delivery     → REST Delivery Points (RDP) + REST Consumers

──────────────────────────────────────────────────────────────────────────────
 API REFERENCE  (Solace Cloud SEMP v2 — endpoints used here)
 Base URL: https://api.solace.cloud/api/v2/msgVpns/{vpnName}
──────────────────────────────────────────────────────────────────────────────
 Object                  Method  Endpoint
 ───────────────────────────────────────────────────────────────────────────
 [A] CREDENTIALS
 Client Profile          GET     /clientProfiles
 Client Profile          POST    /clientProfiles
 Client Profile          GET     /clientProfiles/{clientProfileName}
 Client Profile          PATCH   /clientProfiles/{clientProfileName}
 Client Profile          DELETE  /clientProfiles/{clientProfileName}
 ───────────────────────────────────────────────────────────────────────────
 ACL Profile             GET     /aclProfiles
 ACL Profile             POST    /aclProfiles
 ACL Profile             GET     /aclProfiles/{aclProfileName}
 ACL Profile             PATCH   /aclProfiles/{aclProfileName}
 ACL Profile             DELETE  /aclProfiles/{aclProfileName}
 ACL Profile — Pub Exc.  POST    /aclProfiles/{name}/publishTopicExceptions
 ACL Profile — Sub Exc.  POST    /aclProfiles/{name}/subscribeTopicExceptions
 ───────────────────────────────────────────────────────────────────────────
 Client Username         GET     /clientUsernames
 Client Username         POST    /clientUsernames
 Client Username         GET     /clientUsernames/{clientUsername}
 Client Username         PATCH   /clientUsernames/{clientUsername}
 Client Username         DELETE  /clientUsernames/{clientUsername}
 ───────────────────────────────────────────────────────────────────────────
 [B] MESSAGING OBJECTS
 Queue                   GET     /queues
 Queue                   POST    /queues
 Queue                   GET     /queues/{queueName}
 Queue                   PATCH   /queues/{queueName}
 Queue                   DELETE  /queues/{queueName}
 Queue Subscription      GET     /queues/{queueName}/subscriptions
 Queue Subscription      POST    /queues/{queueName}/subscriptions
 Queue Subscription      DELETE  /queues/{queueName}/subscriptions/{topic}
 ───────────────────────────────────────────────────────────────────────────
 [C] REST DELIVERY POINT
 RDP                     GET     /restDeliveryPoints
 RDP                     POST    /restDeliveryPoints
 RDP                     GET     /restDeliveryPoints/{rdpName}
 RDP                     PATCH   /restDeliveryPoints/{rdpName}
 RDP                     DELETE  /restDeliveryPoints/{rdpName}
 REST Consumer           POST    /restDeliveryPoints/{rdpName}/restConsumers
 REST Consumer           GET     /restDeliveryPoints/{rdpName}/restConsumers/{name}
 REST Consumer           PATCH   /restDeliveryPoints/{rdpName}/restConsumers/{name}
 REST Consumer           DELETE  /restDeliveryPoints/{rdpName}/restConsumers/{name}
 RDP Queue Binding       POST    /restDeliveryPoints/{rdpName}/queueBindings
 RDP Queue Binding       DELETE  /restDeliveryPoints/{rdpName}/queueBindings/{queueName}
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
from typing import Optional
from solace_client import SolaceClient

logger = logging.getLogger(__name__)


class ClusterManager:
    """
    High-level helpers for Solace Cluster Management Objects.

    Parameters
    ----------
    client      : SolaceClient instance
    service_id  : Solace Cloud service/messaging-service id  (used to scope SEMP calls)
    vpn_name    : Message VPN name (default "default")
    """

    def __init__(self, client: SolaceClient, service_id: str, vpn_name: str = "default"):
        self.c          = client
        self.service_id = service_id
        self.vpn_name   = vpn_name
        self._vpn_path  = f"/msgVpns/{vpn_name}"

    # ── internal ──────────────────────────────────────────────────────────────
    def _path(self, suffix: str) -> str:
        return f"{self._vpn_path}{suffix}"

    # ═══════════════════════════════════════════════════════════════════════════
    #  A. CREDENTIALS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Client Profile ────────────────────────────────────────────────────────
    def create_client_profile(self, profile_name: str, **overrides) -> dict:
        """
        POST /msgVpns/{vpn}/clientProfiles
        Creates a Client Profile with sensible defaults (can be overridden).
        """
        payload = {
            "clientProfileName":             profile_name,
            "msgVpnName":                    self.vpn_name,
            "allowBridgeConnectionsEnabled": False,
            "allowGuaranteedMsgSendEnabled": True,
            "allowGuaranteedMsgReceiveEnabled": True,
            "allowTransactedSessionsEnabled": True,
            **overrides,
        }
        logger.info("Creating Client Profile: %s", profile_name)
        resp = self.c.semp_post(self._path("/clientProfiles"), payload)
        logger.info("✓ Client Profile created: %s", profile_name)
        return resp.get("data", resp)

    def delete_client_profile(self, profile_name: str) -> None:
        """DELETE /msgVpns/{vpn}/clientProfiles/{name}"""
        self.c.semp_delete(self._path(f"/clientProfiles/{profile_name}"))
        logger.info("Deleted Client Profile: %s", profile_name)

    # ── ACL Profile ───────────────────────────────────────────────────────────
    def create_acl_profile(self, acl_name: str,
                            client_connect_default: str = "allow",
                            publish_default: str = "allow",
                            subscribe_default: str = "allow") -> dict:
        """
        POST /msgVpns/{vpn}/aclProfiles
        Creates an ACL Profile controlling publish/subscribe permissions.

        Default action options: 'allow' | 'disallow'
        """
        payload = {
            "aclProfileName":                  acl_name,
            "msgVpnName":                      self.vpn_name,
            "clientConnectDefaultAction":       client_connect_default,
            "publishTopicDefaultAction":        publish_default,
            "subscribeTopicDefaultAction":      subscribe_default,
        }
        logger.info("Creating ACL Profile: %s", acl_name)
        resp = self.c.semp_post(self._path("/aclProfiles"), payload)
        logger.info("✓ ACL Profile created: %s", acl_name)
        return resp.get("data", resp)

    def add_publish_exception(self, acl_name: str, topic: str,
                               topic_syntax: str = "smf") -> dict:
        """POST /msgVpns/{vpn}/aclProfiles/{acl}/publishTopicExceptions"""
        payload = {
            "publishTopicException":       topic,
            "publishTopicExceptionSyntax": topic_syntax,
            "aclProfileName":              acl_name,
            "msgVpnName":                  self.vpn_name,
        }
        return self.c.semp_post(
            self._path(f"/aclProfiles/{acl_name}/publishTopicExceptions"), payload
        ).get("data", {})

    def add_subscribe_exception(self, acl_name: str, topic: str,
                                 topic_syntax: str = "smf") -> dict:
        """POST /msgVpns/{vpn}/aclProfiles/{acl}/subscribeTopicExceptions"""
        payload = {
            "subscribeTopicException":       topic,
            "subscribeTopicExceptionSyntax": topic_syntax,
            "aclProfileName":                acl_name,
            "msgVpnName":                    self.vpn_name,
        }
        return self.c.semp_post(
            self._path(f"/aclProfiles/{acl_name}/subscribeTopicExceptions"), payload
        ).get("data", {})

    # ── Client Username ───────────────────────────────────────────────────────
    def create_client_username(self, username: str, password: str,
                                client_profile: str, acl_profile: str,
                                enabled: bool = True) -> dict:
        """
        POST /msgVpns/{vpn}/clientUsernames
        Creates a Client Username (the identity used to connect to the broker).

        Parameters
        ----------
        username       : the client username string
        password       : plaintext password (Solace stores it hashed)
        client_profile : name of an existing Client Profile
        acl_profile    : name of an existing ACL Profile
        enabled        : whether the username is active immediately
        """
        payload = {
            "clientUsername":    username,
            "password":          password,
            "clientProfileName": client_profile,
            "aclProfileName":    acl_profile,
            "enabled":           enabled,
            "msgVpnName":        self.vpn_name,
        }
        logger.info("Creating Client Username: %s", username)
        resp = self.c.semp_post(self._path("/clientUsernames"), payload)
        logger.info("✓ Client Username created: %s", username)
        return resp.get("data", resp)

    def delete_client_username(self, username: str) -> None:
        """DELETE /msgVpns/{vpn}/clientUsernames/{username}"""
        self.c.semp_delete(self._path(f"/clientUsernames/{username}"))
        logger.info("Deleted Client Username: %s", username)

    # ═══════════════════════════════════════════════════════════════════════════
    #  B. MESSAGING OBJECTS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Queue ─────────────────────────────────────────────────────────────────
    def create_queue(self, queue_name: str,
                     owner: str = None,
                     access_type: str = "non-exclusive",
                     max_msg_size_mb: int = 10,
                     max_spool_mb: int = 1500,
                     egress_enabled: bool = True,
                     ingress_enabled: bool = True,
                     **overrides) -> dict:
        """
        POST /msgVpns/{vpn}/queues
        Creates a durable queue on the message broker.

        Parameters
        ----------
        queue_name      : unique name for this queue
        owner           : client username that owns the queue (optional)
        access_type     : 'exclusive' (single consumer) | 'non-exclusive' (competing consumers)
        max_msg_size_mb : maximum individual message size in MB
        max_spool_mb    : maximum total spool usage in MB
        """
        payload = {
            "queueName":         queue_name,
            "msgVpnName":        self.vpn_name,
            "accessType":        access_type,
            "egressEnabled":     egress_enabled,
            "ingressEnabled":    ingress_enabled,
            "maxMsgSize":        min(max_msg_size_mb * 1024 * 1024, 10_000_000),
            "maxMsgSpoolUsage":  max_spool_mb,
            "permission":        "consume",
            **overrides,
        }
        if owner:
            payload["owner"] = owner

        logger.info("Creating Queue: %s (type=%s)", queue_name, access_type)
        resp = self.c.semp_post(self._path("/queues"), payload)
        logger.info("✓ Queue created: %s", queue_name)
        return resp.get("data", resp)

    def add_queue_subscription(self, queue_name: str, topic: str) -> dict:
        """
        POST /msgVpns/{vpn}/queues/{queueName}/subscriptions
        Adds a topic subscription to an existing queue.
        Messages matching this topic will be delivered to the queue.
        """
        payload = {
            "subscriptionTopic": topic,
            "queueName":         queue_name,
            "msgVpnName":        self.vpn_name,
        }
        logger.info("Adding subscription '%s' to queue '%s'", topic, queue_name)
        resp = self.c.semp_post(
            self._path(f"/queues/{queue_name}/subscriptions"), payload
        )
        logger.info("✓ Subscription added")
        return resp.get("data", resp)

    def delete_queue_subscription(self, queue_name: str, topic: str) -> None:
        """DELETE /msgVpns/{vpn}/queues/{queueName}/subscriptions/{topic}"""
        encoded = topic.replace("/", "%2F").replace("*", "%2A").replace(">", "%3E")
        self.c.semp_delete(self._path(f"/queues/{queue_name}/subscriptions/{encoded}"))

    def delete_queue(self, queue_name: str) -> None:
        """DELETE /msgVpns/{vpn}/queues/{queueName}"""
        self.c.semp_delete(self._path(f"/queues/{queue_name}"))
        logger.info("Deleted Queue: %s", queue_name)

    # ═══════════════════════════════════════════════════════════════════════════
    #  C. REST DELIVERY POINT  (push messages out via HTTP/REST to Target System)
    # ═══════════════════════════════════════════════════════════════════════════
    def create_rest_delivery_point(self, rdp_name: str, service_profile: str = "default",
                                    enabled: bool = True) -> dict:
        """
        POST /msgVpns/{vpn}/restDeliveryPoints
        Creates an RDP — the bridge between a queue and an HTTP endpoint.
        """
        payload = {
            "restDeliveryPointName": rdp_name,
            "msgVpnName":            self.vpn_name,
            "clientProfileName":     service_profile,
            "enabled":               enabled,
        }
        logger.info("Creating REST Delivery Point: %s", rdp_name)
        resp = self.c.semp_post(self._path("/restDeliveryPoints"), payload)
        logger.info("✓ RDP created: %s", rdp_name)
        return resp.get("data", resp)

    def create_rest_consumer(self, rdp_name: str, consumer_name: str,
                              host: str, port: int = 443,
                              tls_enabled: bool = True,
                              http_method: str = "post",
                              auth_scheme: str = "none",
                              **overrides) -> dict:
        """
        POST /msgVpns/{vpn}/restDeliveryPoints/{rdpName}/restConsumers
        Defines the target HTTP endpoint that receives messages from the RDP.

        Parameters
        ----------
        rdp_name      : name of the parent RDP
        consumer_name : unique name for this REST consumer
        host          : target hostname or IP
        port          : target port (default 443 for TLS)
        tls_enabled   : whether to use TLS
        http_method   : 'POST' | 'PUT'
        auth_scheme   : 'none' | 'http-basic' | 'http-header' | 'oauth-client-credentials'
        """
        payload = {
            "restConsumerName":      consumer_name,
            "restDeliveryPointName": rdp_name,
            "msgVpnName":            self.vpn_name,
            "remoteHost":            host,
            "remotePort":            port,
            "tlsEnabled":            tls_enabled,
            "httpMethod":            http_method,
            "authenticationScheme":  auth_scheme,
            "enabled":               True,
            **overrides,
        }
        logger.info("Creating REST Consumer: %s → %s:%s", consumer_name, host, port)
        resp = self.c.semp_post(
            self._path(f"/restDeliveryPoints/{rdp_name}/restConsumers"), payload
        )
        logger.info("✓ REST Consumer created: %s", consumer_name)
        return resp.get("data", resp)

    def bind_queue_to_rdp(self, rdp_name: str, queue_name: str,
                           post_request_target: str = "/") -> dict:
        """
        POST /msgVpns/{vpn}/restDeliveryPoints/{rdpName}/queueBindings
        Binds a queue to an RDP — messages in the queue are HTTP-POSTed to the REST consumer.

        post_request_target : URL path appended to the REST consumer's host+port
        """
        payload = {
            "queueBindingName":    queue_name,
            "postRequestTarget":   post_request_target,
            "restDeliveryPointName": rdp_name,
            "msgVpnName":          self.vpn_name,
        }
        logger.info("Binding queue '%s' to RDP '%s'", queue_name, rdp_name)
        resp = self.c.semp_post(
            self._path(f"/restDeliveryPoints/{rdp_name}/queueBindings"), payload
        )
        logger.info("✓ Queue binding created")
        return resp.get("data", resp)

    def delete_rdp(self, rdp_name: str) -> None:
        """DELETE /msgVpns/{vpn}/restDeliveryPoints/{rdpName}"""
        self.c.semp_delete(self._path(f"/restDeliveryPoints/{rdp_name}"))
        logger.info("Deleted RDP: %s", rdp_name)
