"""
Solace Event Portal Designer — Automation Layer
================================================
Wraps the Event Portal Designer REST API exposed by the MCP server
(solace-event-portal-designer-mcp) and used by create_service.py.

All API calls map 1-to-1 to endpoints in:
  https://api.solace.cloud/api/v2/architecture/

──────────────────────────────────────────────────────────────────────────────
 API REFERENCE  (Event Portal Designer — endpoints used here)
──────────────────────────────────────────────────────────────────────────────
 Object               Method  Endpoint
 ─────────────────────────────────────────────────────────────────────────────
 Application Domain   GET     /applicationDomains
 Application Domain   POST    /applicationDomains
 Application Domain   GET     /applicationDomains/{id}
 Application Domain   PATCH   /applicationDomains/{id}
 Application Domain   DELETE  /applicationDomains/{id}
 ─────────────────────────────────────────────────────────────────────────────
 Schema               GET     /schemas
 Schema               POST    /schemas
 Schema               GET     /schemas/{id}
 Schema               PATCH   /schemas/{id}
 Schema               DELETE  /schemas/{id}
 ─────────────────────────────────────────────────────────────────────────────
 Schema Version       GET     /schemaVersions
 Schema Version       POST    /schemaVersions
 Schema Version       GET     /schemaVersions/{id}
 Schema Version       PATCH   /schemaVersions/{id}
 Schema Version       DELETE  /schemaVersions/{id}
 Schema Version       PATCH   /schemaVersions/{id}/state
 ─────────────────────────────────────────────────────────────────────────────
 Event                GET     /events
 Event                POST    /events
 Event                GET     /events/{id}
 Event                PATCH   /events/{id}
 Event                DELETE  /events/{id}
 ─────────────────────────────────────────────────────────────────────────────
 Event Version        GET     /eventVersions
 Event Version        POST    /eventVersions
 Event Version        GET     /eventVersions/{id}
 Event Version        PATCH   /eventVersions/{id}
 Event Version        DELETE  /eventVersions/{id}
 Event Version        PATCH   /eventVersions/{id}/state
 ─────────────────────────────────────────────────────────────────────────────
 Application          GET     /applications
 Application          POST    /applications
 Application          GET     /applications/{id}
 Application          PATCH   /applications/{id}
 Application          DELETE  /applications/{id}
 ─────────────────────────────────────────────────────────────────────────────
 Application Version  GET     /applicationVersions
 Application Version  POST    /applicationVersions
 Application Version  GET     /applicationVersions/{id}
 Application Version  PATCH   /applicationVersions/{id}
 Application Version  DELETE  /applicationVersions/{id}
 Application Version  PATCH   /applicationVersions/{id}/state
 Application Version  GET     /applicationVersions/{id}/asyncApi
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
from typing import Any, Optional
from solace_client import SolaceClient

logger = logging.getLogger(__name__)


class EventPortalManager:
    """High-level helpers for Solace Event Portal Designer objects."""

    def __init__(self, client: SolaceClient):
        self.c = client

    # ═══════════════════════════════════════════════════════════════════════════
    #  APPLICATION DOMAINS
    #  API: GET/POST  /applicationDomains
    #       GET/PATCH/DELETE  /applicationDomains/{id}
    # ═══════════════════════════════════════════════════════════════════════════
    def list_domains(self) -> list[dict]:
        """GET /applicationDomains — list all application domains."""
        resp = self.c.ep_get("/applicationDomains")
        return resp.get("data", [])

    def get_domain(self, domain_id: str) -> dict:
        """GET /applicationDomains/{id}"""
        resp = self.c.ep_get(f"/applicationDomains/{domain_id}")
        return resp.get("data", resp)

    def find_domain_by_name(self, name: str) -> Optional[dict]:
        """Search domain list by name (case-insensitive)."""
        return next((d for d in self.list_domains() if d["name"].lower() == name.lower()), None)

    def create_domain(self, name: str, description: str = "") -> dict:
        """
        POST /applicationDomains
        Creates a new Application Domain (logical namespace for events/apps/schemas).
        Returns the created domain object.
        """
        payload = {"name": name, "description": description}
        logger.info("Creating Application Domain: %s", name)
        resp = self.c.ep_post("/applicationDomains", payload)
        domain = resp.get("data", resp)
        logger.info("✓ Domain created → id=%s", domain.get("id"))
        return domain

    def get_or_create_domain(self, name: str, description: str = "") -> dict:
        """Create domain if it doesn't already exist; return it either way."""
        existing = self.find_domain_by_name(name)
        if existing:
            logger.info("Domain '%s' already exists (id=%s)", name, existing["id"])
            return existing
        return self.create_domain(name, description)

    def delete_domain(self, domain_id: str) -> None:
        """DELETE /applicationDomains/{id}"""
        self.c.ep_delete(f"/applicationDomains/{domain_id}")
        logger.info("Deleted domain id=%s", domain_id)

    # ═══════════════════════════════════════════════════════════════════════════
    #  SCHEMAS
    #  API: GET/POST  /schemas
    #       GET/PATCH/DELETE  /schemas/{id}
    # ═══════════════════════════════════════════════════════════════════════════
    def list_schemas(self, domain_id: str = None) -> list[dict]:
        """GET /schemas  (optionally filtered by applicationDomainId)."""
        params = {}
        if domain_id:
            params["applicationDomainId"] = domain_id
        resp = self.c.ep_get("/schemas", params=params)
        return resp.get("data", [])

    def create_schema(self, name: str, domain_id: str, schema_type: str = "jsonSchema") -> dict:
        """
        POST /schemas
        Creates a Schema object (container — the content goes in a SchemaVersion).

        schema_type options: 'jsonSchema' | 'avro' | 'protobuf' | 'xmlSchema'
        """
        payload = {
            "name":                name,
            "applicationDomainId": domain_id,
            "schemaType":          schema_type,
        }
        logger.info("Creating Schema: %s (type=%s)", name, schema_type)
        resp = self.c.ep_post("/schemas", payload)
        schema = resp.get("data", resp)
        logger.info("✓ Schema created → id=%s", schema.get("id"))
        return schema

    # ═══════════════════════════════════════════════════════════════════════════
    #  SCHEMA VERSIONS
    #  API: GET/POST  /schemaVersions
    #       GET/PATCH/DELETE  /schemaVersions/{id}
    #       PATCH  /schemaVersions/{id}/state
    # ═══════════════════════════════════════════════════════════════════════════
    def create_schema_version(self, schema_id: str, version: str, content: str,
                               description: str = "") -> dict:
        """
        POST /schemaVersions
        Creates a versioned Schema with the actual JSON/Avro/Protobuf content.

        Parameters
        ----------
        schema_id   : id from create_schema()
        version     : semver string, e.g. "1.0.0"
        content     : the schema body as a JSON string
        description : optional human-readable description
        """
        payload = {
            "schemaId":    schema_id,
            "version":     version,
            "description": description,
            "content":     content,
            "displayName": f"v{version}",
        }
        logger.info("Creating SchemaVersion %s for schema=%s", version, schema_id)
        resp = self.c.ep_post("/schemaVersions", payload)
        sv = resp.get("data", resp)
        logger.info("✓ SchemaVersion created → id=%s", sv.get("id"))
        return sv

    def promote_schema_version(self, schema_version_id: str, state: str = "released") -> dict:
        """
        PATCH /schemaVersions/{id}/state
        Promote lifecycle state: 'draft' → 'released' → 'deprecated' → 'retired'
        """
        resp = self.c.ep_patch(f"/schemaVersions/{schema_version_id}/state", {"stateId": state})
        return resp.get("data", resp)

    # ═══════════════════════════════════════════════════════════════════════════
    #  EVENTS
    #  API: GET/POST  /events
    #       GET/PATCH/DELETE  /events/{id}
    # ═══════════════════════════════════════════════════════════════════════════
    def list_events(self, domain_id: str = None) -> list[dict]:
        """GET /events  (optionally filtered by applicationDomainId)."""
        params = {}
        if domain_id:
            params["applicationDomainId"] = domain_id
        resp = self.c.ep_get("/events", params=params)
        return resp.get("data", [])

    def create_event(self, name: str, domain_id: str) -> dict:
        """
        POST /events
        Creates an Event object (the logical event — versions carry the topic/schema).
        """
        payload = {
            "name":                name,
            "applicationDomainId": domain_id,
        }
        logger.info("Creating Event: %s", name)
        resp = self.c.ep_post("/events", payload)
        event = resp.get("data", resp)
        logger.info("✓ Event created → id=%s", event.get("id"))
        return event

    # ═══════════════════════════════════════════════════════════════════════════
    #  EVENT VERSIONS
    #  API: GET/POST  /eventVersions
    #       GET/PATCH/DELETE  /eventVersions/{id}
    #       PATCH  /eventVersions/{id}/state
    # ═══════════════════════════════════════════════════════════════════════════
    def create_event_version(self, event_id: str, version: str,
                              topic: str, schema_version_id: str = None,
                              description: str = "") -> dict:
        """
        POST /eventVersions
        Binds a topic address and (optionally) a schema version to an event.

        Parameters
        ----------
        event_id          : id from create_event()
        version           : semver string, e.g. "1.0.0"
        topic             : Solace topic string, e.g. "mars/orders/{orderId}/created"
        schema_version_id : id from create_schema_version() — optional
        """
        payload: dict[str, Any] = {
            "eventId":     event_id,
            "version":     version,
            "description": description,
            "displayName": f"v{version}",
            "deliveryDescriptor": {
                "brokerType": "solace",
                "address": {
                    "addressLevels": self._topic_to_address_levels(topic),
                    "addressType":   "topic",
                },
            },
        }
        if schema_version_id:
            payload["schemaVersionId"] = schema_version_id

        logger.info("Creating EventVersion %s for event=%s (topic=%s)", version, event_id, topic)
        resp = self.c.ep_post("/eventVersions", payload)
        ev = resp.get("data", resp)
        logger.info("✓ EventVersion created → id=%s", ev.get("id"))
        return ev

    def promote_event_version(self, event_version_id: str, state: str = "released") -> dict:
        """PATCH /eventVersions/{id}/state"""
        resp = self.c.ep_patch(f"/eventVersions/{event_version_id}/state", {"stateId": state})
        return resp.get("data", resp)

    # ═══════════════════════════════════════════════════════════════════════════
    #  APPLICATIONS
    #  API: GET/POST  /applications
    #       GET/PATCH/DELETE  /applications/{id}
    # ═══════════════════════════════════════════════════════════════════════════
    def list_applications(self, domain_id: str = None) -> list[dict]:
        """GET /applications"""
        params = {}
        if domain_id:
            params["applicationDomainId"] = domain_id
        resp = self.c.ep_get("/applications", params=params)
        return resp.get("data", [])

    def create_application(self, name: str, domain_id: str,
                            app_type: str = "standard") -> dict:
        """
        POST /applications
        Creates an Application (logical service — versions carry produce/consume).

        app_type options: 'standard' | 'connector'
        """
        payload = {
            "name":                name,
            "applicationDomainId": domain_id,
            "applicationType":     app_type,
            "brokerType":          "solace",
        }
        logger.info("Creating Application: %s", name)
        resp = self.c.ep_post("/applications", payload)
        app = resp.get("data", resp)
        logger.info("✓ Application created → id=%s", app.get("id"))
        return app

    # ═══════════════════════════════════════════════════════════════════════════
    #  APPLICATION VERSIONS
    #  API: GET/POST  /applicationVersions
    #       GET/PATCH/DELETE  /applicationVersions/{id}
    #       PATCH  /applicationVersions/{id}/state
    #       GET    /applicationVersions/{id}/asyncApi
    # ═══════════════════════════════════════════════════════════════════════════
    def create_application_version(self, app_id: str, version: str,
                                    declared_produced_event_version_ids: list[str] = None,
                                    declared_consumed_event_version_ids: list[str] = None,
                                    description: str = "") -> dict:
        """
        POST /applicationVersions
        Links an application to the events it produces and/or consumes.

        Parameters
        ----------
        app_id                              : id from create_application()
        version                             : semver string, e.g. "1.0.0"
        declared_produced_event_version_ids : list of event-version ids this app publishes
        declared_consumed_event_version_ids : list of event-version ids this app subscribes to
        """
        payload: dict[str, Any] = {
            "applicationId": app_id,
            "version":       version,
            "description":   description,
            "displayName":   f"v{version}",
            "declaredProducedEventVersionIds": declared_produced_event_version_ids or [],
            "declaredConsumedEventVersionIds": declared_consumed_event_version_ids or [],
        }
        logger.info("Creating ApplicationVersion %s for app=%s", version, app_id)
        resp = self.c.ep_post("/applicationVersions", payload)
        av = resp.get("data", resp)
        logger.info("✓ ApplicationVersion created → id=%s", av.get("id"))
        return av

    def promote_application_version(self, app_version_id: str, state: str = "released") -> dict:
        """PATCH /applicationVersions/{id}/state"""
        resp = self.c.ep_patch(f"/applicationVersions/{app_version_id}/state", {"stateId": state})
        return resp.get("data", resp)

    def get_asyncapi(self, app_version_id: str, format: str = "json") -> str:
        """
        GET /applicationVersions/{id}/asyncApi
        Export the AsyncAPI spec for a deployed application version.

        format: 'json' | 'yaml'
        """
        resp = self.c.ep_get(
            f"/applicationVersions/{app_version_id}/asyncApi",
            params={"format": format}
        )
        return resp

    # ═══════════════════════════════════════════════════════════════════════════
    #  Internal helpers
    # ═══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _topic_to_address_levels(topic: str) -> list[dict]:
        """
        Convert a Solace topic string into addressLevels array.
        e.g. "mars/orders/{orderId}/created" →
             [{"name":"mars"}, {"name":"orders"}, {"name":"{orderId}","addressLevelType":"variable"}, {"name":"created"}]
        """
        levels = []
        for part in topic.split("/"):
            if part.startswith("{") and part.endswith("}"):
                levels.append({"name": part[1:-1], "addressLevelType": "variable"})
            else:
                levels.append({"name": part, "addressLevelType": "literal"})
        return levels
