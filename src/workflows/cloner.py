"""
src/workflows/cloner.py — Country Config Cloner
=================================================
Takes a config exported by Exporter and produces a new config for a
different country/region by:

  1. Replacing every occurrence of the source country code with the target
     country code across ALL string values (names, topics, descriptions,
     datacenter hints, host patterns, etc.).

  2. Updating service-level fields (name, datacenter, serviceId).

  3. Auto-generating secure random passwords for any client username that
     has an empty password field (passwords are never exported).

  4. Optionally writing the result to a config JSON file ready for:
       python3 solace.py provision run --config config/<country>/service.json

Substitution rules
------------------
  "mars-AU-profile"      →  "mars-SG-profile"
  "MarsAutomation-AU"    →  "MarsAutomation-SG"
  "mars-au-orders-q"     →  "mars-sg-orders-q"
  "mars/au/orders/>"     →  "mars/sg/orders/>"
  "target-au.example.com"→  "target-sg.example.com"

The VPN name is NOT substituted — it is always the auto-assigned name of the
target service and is filled in at provisioning time.

Usage
-----
    from workflows.cloner import Cloner
    c = Cloner()
    cfg = c.clone(source_config, target_country="SG",
                  datacenter="aks-australiaeast",
                  service_name="mars-automation-sg")
    c.clone_to_file("config/au/service.json",
                    "config/sg/service.json",
                    target_country="SG",
                    datacenter="aks-australiaeast",
                    service_name="mars-automation-sg")
"""

from __future__ import annotations
import copy
import json
import logging
import secrets
import string
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Cloner:
    """
    Clones a service config to a new country by substituting the country code
    throughout all string values and updating service metadata.
    """

    def clone(self,
              source_config:      dict,
              target_country:     str,
              datacenter:         str  = None,
              service_name:       str  = None,
              service_id:         str  = None,
              target_env:         str  = None,
              generate_passwords: bool = True) -> dict:
        """
        Clone *source_config* to *target_country*.

        Parameters
        ----------
        source_config      : Dict exported by Exporter (must have 'sourceCountry')
        target_country     : Two-letter country code to clone to (e.g. 'SG', 'DE')
        datacenter         : Target datacenter ID (e.g. 'aks-australiaeast')
        service_name       : Override the service name in the clone
        service_id         : Use an existing service (skip creation) — optional
        target_env         : Environment label (defaults to target_country.lower())
        generate_passwords : Auto-generate passwords for client usernames with empty passwords

        Returns new config dict.
        """
        src_country = source_config.get("sourceCountry", "")
        if not src_country:
            raise ValueError(
                "'sourceCountry' missing in config. "
                "Export with --country <XX> to tag the source.")

        src = src_country.upper()
        tgt = target_country.upper()

        if src == tgt:
            raise ValueError(f"Source and target country are the same: {src}")

        logger.info("Cloning  %s  →  %s", src, tgt)

        # Deep copy then substitute
        cloned = self._deep_substitute(copy.deepcopy(source_config), src, tgt)

        # Top-level metadata
        cloned["sourceCountry"] = src
        cloned["targetCountry"] = tgt
        cloned["environment"]   = target_env or tgt.lower()

        # Service fields
        svc = cloned.setdefault("service", {})
        if datacenter:
            svc["datacenterId"] = datacenter
        if service_name:
            svc["name"] = service_name
        if service_id:
            svc["serviceId"] = service_id
        else:
            svc["serviceId"] = ""   # blank = create a new service

        # VPN name is always set at provision time — clear it
        cm = cloned.setdefault("clusterManagement", {})
        cm["vpnName"] = ""   # filled in by Provisioner.provision_cluster()

        # Passwords
        if generate_passwords:
            generated: list[tuple[str, str]] = []
            for u in cm.get("clientUsernames", []):
                if not u.get("password"):
                    pw = self._gen_password()
                    u["password"] = pw
                    generated.append((u["name"], pw))

            if generated:
                logger.info("")
                logger.info("  ⚠️  Generated passwords (save these now):")
                for name, pw in generated:
                    logger.info("      %-35s  %s", name, pw)
                logger.info("")

        logger.info("✓ Clone ready  source=%s  target=%s", src, tgt)
        return cloned

    def clone_to_file(self,
                      source_path:  str,
                      output_path:  str,
                      **kwargs) -> dict:
        """
        Load source config from *source_path*, clone it, write to *output_path*.
        All **kwargs are passed to clone().
        """
        source = json.loads(Path(source_path).read_text())
        cloned = self.clone(source, **kwargs)
        out    = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cloned, indent=2))
        logger.info("✓ Cloned config  →  %s", output_path)
        return cloned

    # ── substitution ───────────────────────────────────────────────────────────
    def _deep_substitute(self, obj, src: str, tgt: str):
        """
        Recursively replace src country code with tgt across the entire config.
        Handles all three case variants:
          AU  →  SG   (upper)
          au  →  sg   (lower)
          Au  →  Sg   (title)
        """
        if isinstance(obj, str):
            result = obj
            for s, t in [
                (src.upper(),     tgt.upper()),
                (src.lower(),     tgt.lower()),
                (src.capitalize(), tgt.capitalize()),
            ]:
                result = result.replace(s, t)
            return result
        elif isinstance(obj, dict):
            return {k: self._deep_substitute(v, src, tgt) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_substitute(item, src, tgt) for item in obj]
        return obj   # int, float, bool, None — unchanged

    # ── password generator ────────────────────────────────────────────────────
    @staticmethod
    def _gen_password(length: int = 20) -> str:
        """
        Generate a cryptographically random password that satisfies most
        Solace password policies (upper + lower + digit + special).
        """
        upper   = string.ascii_uppercase
        lower   = string.ascii_lowercase
        digits  = string.digits
        # Solace SEMP rejects: : ( ) " ; ' < > , ` \ & |
        # Keep only safe special chars that pass every broker policy
        special = "!@#$%^*-_=+?"
        all_ch  = upper + lower + digits + special

        # Guarantee at least one of each category
        pwd = [
            secrets.choice(upper),
            secrets.choice(lower),
            secrets.choice(digits),
            secrets.choice(special),
        ]
        pwd += [secrets.choice(all_ch) for _ in range(length - 4)]

        # Shuffle so the guaranteed chars aren't always at the start
        secrets.SystemRandom().shuffle(pwd)
        return "".join(pwd)

    # ── diff helper ───────────────────────────────────────────────────────────
    @staticmethod
    def diff_summary(source: dict, cloned: dict) -> str:
        """
        Return a human-readable summary of what changed between source and clone.
        Useful for review before provisioning.
        """
        src_country = source.get("sourceCountry", "?")
        tgt_country = cloned.get("targetCountry", "?")
        lines = [
            f"  Source country : {src_country}",
            f"  Target country : {tgt_country}",
            "",
            f"  Source service : {source.get('service', {}).get('name', '')}",
            f"  Target service : {cloned.get('service', {}).get('name', '')}",
            f"  Datacenter     : {cloned.get('service', {}).get('datacenterId', '(unchanged)')}",
            "",
        ]
        # EP objects
        src_ep = source.get("eventPortal", {})
        tgt_ep = cloned.get("eventPortal", {})
        lines += [
            f"  EP domain      : {src_ep.get('domainName', '')}  →  {tgt_ep.get('domainName', '')}",
        ]
        for key, label in [("schemas", "Schemas"), ("events", "Events"),
                            ("applications", "Applications")]:
            src_items = [x.get("name", "") for x in src_ep.get(key, [])]
            tgt_items = [x.get("name", "") for x in tgt_ep.get(key, [])]
            for s, t in zip(src_items, tgt_items):
                lines.append(f"    {label:<14} {s:<35} →  {t}")

        # Cluster objects
        src_cm = source.get("clusterManagement", {})
        tgt_cm = cloned.get("clusterManagement", {})
        lines.append("")
        for key, label in [("clientProfiles", "Profiles"),
                            ("aclProfiles", "ACLs"),
                            ("clientUsernames", "Usernames"),
                            ("queues", "Queues"),
                            ("restDeliveryPoints", "RDPs")]:
            src_items = [x.get("name", "") for x in src_cm.get(key, [])]
            tgt_items = [x.get("name", "") for x in tgt_cm.get(key, [])]
            for s, t in zip(src_items, tgt_items):
                lines.append(f"    {label:<14} {s:<35} →  {t}")

        return "\n".join(lines)
