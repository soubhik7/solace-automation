"""
src/api/event_portal.py — Solace Event Portal Designer API (full CRUD)
=======================================================================
Base URL: https://api.solace.cloud/api/v2/architecture

──────────────────────────────────────────────────────────────────────────
 OBJECT            METHOD   ENDPOINT
──────────────────────────────────────────────────────────────────────────
 ApplicationDomain GET      /applicationDomains
                   POST     /applicationDomains
                   GET      /applicationDomains/{id}
                   PATCH    /applicationDomains/{id}
                   DELETE   /applicationDomains/{id}
 ──────────────────────────────────────────────────────────────────────
 Schema            GET      /schemas
                   POST     /schemas
                   GET      /schemas/{id}
                   PATCH    /schemas/{id}
                   DELETE   /schemas/{id}
 SchemaVersion     GET      /schemaVersions
                   POST     /schemaVersions
                   GET      /schemaVersions/{id}
                   PATCH    /schemaVersions/{id}
                   DELETE   /schemaVersions/{id}
                   PATCH    /schemaVersions/{id}/state
 ──────────────────────────────────────────────────────────────────────
 Event             GET      /events
                   POST     /events
                   GET      /events/{id}
                   PATCH    /events/{id}
                   DELETE   /events/{id}
 EventVersion      GET      /eventVersions
                   POST     /eventVersions
                   GET      /eventVersions/{id}
                   PATCH    /eventVersions/{id}
                   DELETE   /eventVersions/{id}
                   PATCH    /eventVersions/{id}/state
 ──────────────────────────────────────────────────────────────────────
 Application       GET      /applications
                   POST     /applications
                   GET      /applications/{id}
                   PATCH    /applications/{id}
                   DELETE   /applications/{id}
 ApplicationVersion GET     /applicationVersions
                   POST     /applicationVersions
                   GET      /applicationVersions/{id}
                   PATCH    /applicationVersions/{id}
                   DELETE   /applicationVersions/{id}
                   PATCH    /applicationVersions/{id}/state
                   GET      /applicationVersions/{id}/asyncApi
──────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import json
import logging
from typing import Optional
from client import SolaceClient

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────
def _data(resp): return resp.get("data", resp)
def _list(resp): return resp.get("data", [])


class EventPortalAPI:
    def __init__(self, client: SolaceClient):
        self.c = client

    # ═══════════════════════════════════════════════════════════════════════
    #  APPLICATION DOMAINS
    # ═══════════════════════════════════════════════════════════════════════
    def list_domains(self, name: str = None) -> list[dict]:
        params = {"name": name} if name else {}
        return _list(self.c.ep_get("/applicationDomains", params=params))

    def get_domain(self, domain_id: str) -> dict:
        return _data(self.c.ep_get(f"/applicationDomains/{domain_id}"))

    def find_domain(self, name: str) -> Optional[dict]:
        return next((d for d in self.list_domains() if d["name"].lower() == name.lower()), None)

    def create_domain(self, name: str, description: str = "") -> dict:
        logger.info("Creating domain '%s'", name)
        d = _data(self.c.ep_post("/applicationDomains", {"name": name, "description": description}))
        logger.info("  ✓ domain id=%s", d.get("id"))
        return d

    def get_or_create_domain(self, name: str, description: str = "") -> dict:
        existing = self.find_domain(name)
        if existing:
            logger.info("  Domain '%s' already exists (id=%s)", name, existing["id"])
            return existing
        return self.create_domain(name, description)

    def update_domain(self, domain_id: str, **fields) -> dict:
        return _data(self.c.ep_patch(f"/applicationDomains/{domain_id}", fields))

    def delete_domain(self, domain_id: str) -> None:
        self.c.ep_delete(f"/applicationDomains/{domain_id}")
        logger.info("  ✓ Deleted domain id=%s", domain_id)

    # ═══════════════════════════════════════════════════════════════════════
    #  SCHEMAS
    # ═══════════════════════════════════════════════════════════════════════
    def list_schemas(self, domain_id: str = None) -> list[dict]:
        params = {"applicationDomainId": domain_id} if domain_id else {}
        return _list(self.c.ep_get("/schemas", params=params))

    def get_schema(self, schema_id: str) -> dict:
        return _data(self.c.ep_get(f"/schemas/{schema_id}"))

    def create_schema(self, name: str, domain_id: str,
                      schema_type: str = "jsonSchema") -> dict:
        """schema_type: jsonSchema | avro | protobuf | xmlSchema"""
        logger.info("Creating schema '%s' (type=%s)", name, schema_type)
        d = _data(self.c.ep_post("/schemas", {
            "name": name,
            "applicationDomainId": domain_id,
            "schemaType": schema_type,
        }))
        logger.info("  ✓ schema id=%s", d.get("id"))
        return d

    def find_schema(self, name: str, domain_id: str = None) -> Optional[dict]:
        return next((s for s in self.list_schemas(domain_id=domain_id)
                     if s["name"].lower() == name.lower()), None)

    def get_or_create_schema(self, name: str, domain_id: str,
                              schema_type: str = "jsonSchema") -> dict:
        existing = self.find_schema(name, domain_id=domain_id)
        if existing:
            logger.info("  Schema '%s' already exists (id=%s)", name, existing["id"])
            return existing
        return self.create_schema(name, domain_id, schema_type)

    def update_schema(self, schema_id: str, **fields) -> dict:
        return _data(self.c.ep_patch(f"/schemas/{schema_id}", fields))

    def delete_schema(self, schema_id: str) -> None:
        self.c.ep_delete(f"/schemas/{schema_id}")
        logger.info("  ✓ Deleted schema id=%s", schema_id)

    # Schema Versions
    def list_schema_versions(self, schema_id: str = None) -> list[dict]:
        params = {"schemaId": schema_id} if schema_id else {}
        return _list(self.c.ep_get("/schemaVersions", params=params))

    def get_schema_version(self, version_id: str) -> dict:
        return _data(self.c.ep_get(f"/schemaVersions/{version_id}"))

    def create_schema_version(self, schema_id: str, version: str,
                               content: str, description: str = "") -> dict:
        logger.info("Creating schema version %s for schema=%s", version, schema_id)
        d = _data(self.c.ep_post("/schemaVersions", {
            "schemaId":    schema_id,
            "version":     version,
            "description": description,
            "content":     content,
            "displayName": f"v{version}",
        }))
        logger.info("  ✓ schema version id=%s", d.get("id"))
        return d

    def update_schema_version_state(self, version_id: str,
                                     state: str = "released") -> dict:
        """state: draft | released | deprecated | retired"""
        return _data(self.c.ep_patch(f"/schemaVersions/{version_id}/state",
                                     {"stateId": state}))

    def delete_schema_version(self, version_id: str) -> None:
        self.c.ep_delete(f"/schemaVersions/{version_id}")

    # ═══════════════════════════════════════════════════════════════════════
    #  EVENTS
    # ═══════════════════════════════════════════════════════════════════════
    def list_events(self, domain_id: str = None, name: str = None) -> list[dict]:
        params = {}
        if domain_id: params["applicationDomainId"] = domain_id
        if name:      params["name"] = name
        return _list(self.c.ep_get("/events", params=params))

    def get_event(self, event_id: str) -> dict:
        return _data(self.c.ep_get(f"/events/{event_id}"))

    def create_event(self, name: str, domain_id: str,
                     description: str = "") -> dict:
        logger.info("Creating event '%s'", name)
        d = _data(self.c.ep_post("/events", {
            "name": name,
            "applicationDomainId": domain_id,
            "description": description,
        }))
        logger.info("  ✓ event id=%s", d.get("id"))
        return d

    def find_event(self, name: str, domain_id: str = None) -> Optional[dict]:
        return next((e for e in self.list_events(domain_id=domain_id)
                     if e["name"].lower() == name.lower()), None)

    def get_or_create_event(self, name: str, domain_id: str,
                             description: str = "") -> dict:
        existing = self.find_event(name, domain_id=domain_id)
        if existing:
            logger.info("  Event '%s' already exists (id=%s)", name, existing["id"])
            return existing
        return self.create_event(name, domain_id, description)

    def update_event(self, event_id: str, **fields) -> dict:
        return _data(self.c.ep_patch(f"/events/{event_id}", fields))

    def delete_event(self, event_id: str) -> None:
        self.c.ep_delete(f"/events/{event_id}")

    # Event Versions
    def list_event_versions(self, event_id: str = None) -> list[dict]:
        params = {"eventId": event_id} if event_id else {}
        return _list(self.c.ep_get("/eventVersions", params=params))

    def get_event_version(self, version_id: str) -> dict:
        return _data(self.c.ep_get(f"/eventVersions/{version_id}"))

    def create_event_version(self, event_id: str, version: str, topic: str,
                              schema_version_id: str = None,
                              description: str = "") -> dict:
        logger.info("Creating event version %s (topic=%s)", version, topic)
        payload = {
            "eventId":     event_id,
            "version":     version,
            "description": description,
            "displayName": f"v{version}",
            "deliveryDescriptor": {
                "brokerType": "solace",
                "address": {
                    "addressType":   "topic",
                    "addressLevels": self._topic_levels(topic),
                },
            },
        }
        if schema_version_id:
            payload["schemaVersionId"] = schema_version_id
        d = _data(self.c.ep_post("/eventVersions", payload))
        logger.info("  ✓ event version id=%s", d.get("id"))
        return d

    def update_event_version_state(self, version_id: str,
                                    state: str = "released") -> dict:
        return _data(self.c.ep_patch(f"/eventVersions/{version_id}/state",
                                     {"stateId": state}))

    def delete_event_version(self, version_id: str) -> None:
        self.c.ep_delete(f"/eventVersions/{version_id}")

    # ═══════════════════════════════════════════════════════════════════════
    #  APPLICATIONS
    # ═══════════════════════════════════════════════════════════════════════
    def list_applications(self, domain_id: str = None, name: str = None) -> list[dict]:
        params = {}
        if domain_id: params["applicationDomainId"] = domain_id
        if name:      params["name"] = name
        return _list(self.c.ep_get("/applications", params=params))

    def get_application(self, app_id: str) -> dict:
        return _data(self.c.ep_get(f"/applications/{app_id}"))

    def create_application(self, name: str, domain_id: str,
                            app_type: str = "standard",
                            description: str = "") -> dict:
        """app_type: standard | connector"""
        logger.info("Creating application '%s'", name)
        d = _data(self.c.ep_post("/applications", {
            "name":                name,
            "applicationDomainId": domain_id,
            "applicationType":     app_type,
            "brokerType":          "solace",
            "description":         description,
        }))
        logger.info("  ✓ application id=%s", d.get("id"))
        return d

    def find_application(self, name: str, domain_id: str = None) -> Optional[dict]:
        return next((a for a in self.list_applications(domain_id=domain_id)
                     if a["name"].lower() == name.lower()), None)

    def get_or_create_application(self, name: str, domain_id: str,
                                   app_type: str = "standard",
                                   description: str = "") -> dict:
        existing = self.find_application(name, domain_id=domain_id)
        if existing:
            logger.info("  Application '%s' already exists (id=%s)", name, existing["id"])
            return existing
        return self.create_application(name, domain_id, app_type, description)

    def update_application(self, app_id: str, **fields) -> dict:
        return _data(self.c.ep_patch(f"/applications/{app_id}", fields))

    def delete_application(self, app_id: str) -> None:
        self.c.ep_delete(f"/applications/{app_id}")

    # Application Versions
    def list_application_versions(self, app_id: str = None) -> list[dict]:
        params = {"applicationId": app_id} if app_id else {}
        return _list(self.c.ep_get("/applicationVersions", params=params))

    def get_application_version(self, version_id: str) -> dict:
        return _data(self.c.ep_get(f"/applicationVersions/{version_id}"))

    def create_application_version(self, app_id: str, version: str,
                                    produces: list[str] = None,
                                    consumes: list[str] = None,
                                    description: str = "") -> dict:
        logger.info("Creating app version %s (produces=%d, consumes=%d)",
                    version, len(produces or []), len(consumes or []))
        d = _data(self.c.ep_post("/applicationVersions", {
            "applicationId":                     app_id,
            "version":                           version,
            "description":                       description,
            "displayName":                       f"v{version}",
            "declaredProducedEventVersionIds":   produces or [],
            "declaredConsumedEventVersionIds":   consumes or [],
        }))
        logger.info("  ✓ app version id=%s", d.get("id"))
        return d

    def update_application_version_state(self, version_id: str,
                                          state: str = "released") -> dict:
        return _data(self.c.ep_patch(f"/applicationVersions/{version_id}/state",
                                     {"stateId": state}))

    def get_asyncapi(self, version_id: str, fmt: str = "json") -> dict:
        """GET /applicationVersions/{id}/asyncApi — export AsyncAPI spec."""
        return self.c.ep_get(f"/applicationVersions/{version_id}/asyncApi",
                             params={"format": fmt})

    def delete_application_version(self, version_id: str) -> None:
        self.c.ep_delete(f"/applicationVersions/{version_id}")

    # ── internal ───────────────────────────────────────────────────────────
    @staticmethod
    def _topic_levels(topic: str) -> list[dict]:
        levels = []
        for part in topic.split("/"):
            if part.startswith("{") and part.endswith("}"):
                levels.append({"name": part[1:-1], "addressLevelType": "variable"})
            else:
                levels.append({"name": part, "addressLevelType": "literal"})
        return levels
