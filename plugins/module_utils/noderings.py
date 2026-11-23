# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared NodeRings API client for the noderings.cloud collection."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import random
import time
import uuid

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.common.text.converters import to_native, to_text
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
from ansible.module_utils.six.moves.urllib.parse import quote, urlencode
from ansible.module_utils.urls import open_url

COLLECTION_VERSION = "0.1.0"
DEFAULT_API_URL = "https://api.noderings.com"

# gRPC status codes carried in the API's error bodies.
CODE_INVALID_ARGUMENT = 3
CODE_DEADLINE_EXCEEDED = 4
CODE_NOT_FOUND = 5
CODE_ALREADY_EXISTS = 6
CODE_PERMISSION_DENIED = 7
CODE_RESOURCE_EXHAUSTED = 8
CODE_FAILED_PRECONDITION = 9
CODE_UNAUTHENTICATED = 16

# Fields never echoed back in error messages or logs.
SENSITIVE_KEYS = frozenset(["password", "value", "token", "secret", "clientSecret"])


def noderings_argument_spec():
    """Connection options shared by every module (see the noderings doc fragment)."""
    return dict(
        api_url=dict(
            type="str",
            fallback=(env_fallback, ["NODERINGS_API_URL"]),
            default=DEFAULT_API_URL,
        ),
        api_token=dict(
            type="str",
            no_log=True,
            aliases=["token"],
            fallback=(env_fallback, ["NODERINGS_TOKEN", "NODERINGS_API_TOKEN", "NR_API_TOKEN"]),
        ),
        organization_id=dict(
            type="str",
            fallback=(env_fallback, ["NODERINGS_ORGANIZATION_ID", "NR_ORGANIZATION_ID"]),
        ),
        api_timeout=dict(type="int", default=60),
        api_retries=dict(type="int", default=5),
        validate_certs=dict(type="bool", default=True),
    )


class NodeRingsError(Exception):
    """An error returned by the NodeRings API."""

    def __init__(self, status, code=0, message="", details=None, method="", path=""):
        self.status = status
        self.code = code
        self.message = (message or "").strip()
        self.details = details or []
        self.method = method
        self.path = path
        super(NodeRingsError, self).__init__(self.__str__())

    def quota_info(self):
        for d in self.details:
            if not isinstance(d, dict):
                continue
            if str(d.get("@type", "")).endswith("google.rpc.ErrorInfo") and str(d.get("reason", "")).endswith("LIMIT_REACHED"):
                return d
        return None

    def is_quota(self):
        return self.quota_info() is not None

    def __str__(self):
        msg = self.message or "HTTP %s" % self.status
        q = self.quota_info()
        if q:
            meta = q.get("metadata") or {}
            if "limit" in meta:
                return "%s (quota %s: %s of %s used)" % (msg, meta.get("limit_key"), meta.get("current"), meta.get("limit"))
        where = " on %s %s" % (self.method, self.path) if self.method else ""
        return "%s (HTTP %s%s)" % (msg, self.status, where)


def is_not_found(err):
    return isinstance(err, NodeRingsError) and err.code == CODE_NOT_FOUND


def is_already_exists(err):
    return isinstance(err, NodeRingsError) and err.code == CODE_ALREADY_EXISTS


def is_busy(err):
    """The API refuses changes while a VM operation is running."""
    return (
        isinstance(err, NodeRingsError)
        and err.code == CODE_FAILED_PRECONDITION
        and "in progress" in err.message.lower()
    )


def is_ambiguous(err):
    """True when a request may or may not have been applied (lost response)."""
    if isinstance(err, NodeRingsError):
        if err.status in (502, 503, 504):
            return True
        if err.status == 429:
            return not err.is_quota()
        return False
    return isinstance(err, (URLError, IOError, OSError))


def decode_error(status, body, method="", path=""):
    code, message, details = 0, "", []
    try:
        data = json.loads(to_text(body or b"{}", errors="surrogate_or_strict"))
        if isinstance(data, dict):
            code = int(data.get("code") or 0)
            message = data.get("message") or ""
            details = data.get("details") or []
        else:
            message = to_text(body)[:300]
    except (ValueError, TypeError):
        message = to_text(body or b"", errors="surrogate_or_replace").strip()[:300]
    if not code:
        code = {404: CODE_NOT_FOUND, 409: CODE_ALREADY_EXISTS, 403: CODE_PERMISSION_DENIED, 401: CODE_UNAUTHENTICATED}.get(status, 0)
    return NodeRingsError(status, code, message, details, method, path)


def new_uuid():
    return str(uuid.uuid4())


def path_escape(value):
    return quote(to_native(value), safe="")


def trim_enum(value, prefix):
    """BILLING_TYPE_USAGE -> usage."""
    if not value:
        return ""
    value = to_text(value)
    if value.startswith(prefix):
        value = value[len(prefix):]
    if value == "UNSPECIFIED":
        return ""
    return value.lower()


class NodeRingsClient(object):
    """Small JSON client for the NodeRings public API."""

    def __init__(self, api_url=DEFAULT_API_URL, token=None, organization_id=None, timeout=60, retries=5,
                 validate_certs=True, user_agent=None, opener=None, sleep=time.sleep):
        if not token or not token.strip():
            raise ValueError(
                "A NodeRings API token is required: set api_token or the NODERINGS_TOKEN environment variable. "
                "Create a service-account token in the console under Organization > Service accounts."
            )
        self.base = (api_url or DEFAULT_API_URL).rstrip("/")
        if not (self.base.startswith("https://") or self.base.startswith("http://")):
            raise ValueError("api_url must be an absolute URL such as %s" % DEFAULT_API_URL)
        self.token = token.strip()
        self.organization_id = (organization_id or "").strip()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.validate_certs = validate_certs
        self.user_agent = user_agent or "ansible-collection-noderings/%s" % COLLECTION_VERSION
        self._open = opener or open_url
        self._sleep = sleep

    # -- transport -----------------------------------------------------------------

    def _backoff(self, attempt):
        delay = min(0.5 * (2 ** min(attempt, 10)), 10.0)
        return delay / 2 + random.uniform(0, delay / 2)

    def _retryable(self, err, retry_unavailable):
        if isinstance(err, NodeRingsError):
            if err.status == 429:
                return not err.is_quota()
            if err.status in (502, 504):
                return True
            if err.status == 503:
                return retry_unavailable
            return False
        return True  # connection errors

    def request(self, method, path, query=None, body=None, retry_unavailable=None, retries=None):
        """Send one API request and return the decoded JSON body (or {}).

        GET requests retry on 503 by default. Writes do not, because some write
        endpoints (DNS) report validation errors as 503.
        """
        if retry_unavailable is None:
            retry_unavailable = method == "GET"
        max_retries = self.retries if retries is None else retries
        url = self.base + path
        if query:
            pairs = []
            for k in sorted(query):
                v = query[k]
                if v is None or v == "":
                    continue
                if isinstance(v, (list, tuple)):
                    for item in v:
                        pairs.append((k, to_native(item)))
                elif isinstance(v, bool):
                    pairs.append((k, "true" if v else "false"))
                else:
                    pairs.append((k, to_native(v)))
            if pairs:
                url += "?" + urlencode(pairs)
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        if self.organization_id:
            headers["X-Organization-ID"] = self.organization_id

        attempt = 0
        while True:
            try:
                resp = self._open(url, method=method, data=data, headers=headers, timeout=self.timeout,
                                  validate_certs=self.validate_certs, http_agent=self.user_agent)
                raw = resp.read()
                if not raw or not raw.strip():
                    return {}
                return json.loads(to_text(raw, errors="surrogate_or_strict"))
            except HTTPError as e:
                try:
                    raw = e.read()
                except Exception:
                    raw = b""
                err = decode_error(e.code, raw, method, path)
            except (URLError, IOError, OSError) as e:
                err = e
            if attempt >= max_retries or not self._retryable(err, retry_unavailable):
                raise err
            self._sleep(self._backoff(attempt))
            attempt += 1

    def get(self, path, query=None):
        return self.request("GET", path, query=query)

    def list_all(self, path, key, query=None):
        q = {"page": "0", "pageSize": "-1"}
        q.update(query or {})
        return self.get(path, q).get(key) or []

    def list_paged(self, path, key, query=None, page_size=100):
        out = []
        page = 0
        while True:
            q = {"page": str(page), "pageSize": str(page_size)}
            q.update(query or {})
            data = self.get(path, q)
            items = data.get(key) or []
            out.extend(items)
            total = int(data.get("totalCount") or 0)
            if len(items) < page_size or len(out) >= total:
                return out
            page += 1

    # -- organization --------------------------------------------------------------

    def get_organization(self):
        return self.get("/v1/organization").get("organization")

    def list_organizations(self):
        return self.get("/v1/organizations", {"page": "0", "pageSize": "100"}).get("organizations") or []

    # -- SSH keys ------------------------------------------------------------------

    def list_ssh_keys(self):
        return self.list_all("/v1/ssh-keys", "sshKeys")

    def get_ssh_key(self, key_id):
        return self.get("/v1/ssh-keys/" + path_escape(key_id)).get("sshKey")

    def create_ssh_key(self, name, public_key):
        return self.request("POST", "/v1/ssh-keys", body={"name": name, "publicKey": public_key}).get("sshKey")

    def delete_ssh_key(self, key_id):
        self.request("DELETE", "/v1/ssh-keys/" + path_escape(key_id))

    # -- DNS -----------------------------------------------------------------------

    def zone_path(self, zone_id):
        return "/v1/dns/zones/" + path_escape(zone_id)

    def list_dns_zones(self):
        return self.list_all("/v1/dns/zones", "zones")

    def get_dns_zone(self, zone_id):
        return self.get(self.zone_path(zone_id)).get("zone")

    def create_dns_zone(self, name):
        return self.request("POST", "/v1/dns/zones", body={"name": name}).get("zone")

    def delete_dns_zone(self, zone_id, force=False):
        self.request("DELETE", self.zone_path(zone_id), query={"force": "true"} if force else None)

    def check_dns_zone_delegation(self, zone_id):
        return self.request("POST", self.zone_path(zone_id) + "/check-delegation", body={}, retry_unavailable=True).get("zone")

    def list_dns_records(self, zone_id, name=None, rrtype=None):
        return self.list_paged(self.zone_path(zone_id) + "/records", "records", {"name": name, "type": rrtype})

    def upsert_dns_record(self, zone_id, record):
        return self.request("PUT", self.zone_path(zone_id) + "/records", body={"record": record})

    def delete_dns_record(self, zone_id, name, rrtype):
        self.request("DELETE", self.zone_path(zone_id) + "/records", query={"name": name, "type": rrtype})

    def list_dns_geo_records(self, zone_id):
        return self.get(self.zone_path(zone_id) + "/geo-records").get("records") or []

    def upsert_dns_geo_record(self, zone_id, record):
        return self.request("PUT", self.zone_path(zone_id) + "/geo-records", body={"record": record})

    def delete_dns_geo_record(self, zone_id, name, rrtype):
        self.request("DELETE", self.zone_path(zone_id) + "/geo-records", query={"name": name, "type": rrtype})

    def get_dnssec(self, zone_id):
        return self.get(self.zone_path(zone_id) + "/dnssec")

    def enable_dnssec(self, zone_id):
        return self.request("POST", self.zone_path(zone_id) + "/dnssec/enable", body={})

    def disable_dnssec(self, zone_id, force=False):
        return self.request("POST", self.zone_path(zone_id) + "/dnssec/disable", body={"force": force})

    def check_dnssec_ds(self, zone_id):
        return self.request("POST", self.zone_path(zone_id) + "/dnssec/check-ds", body={}, retry_unavailable=True)

    # -- firewall ------------------------------------------------------------------

    def list_firewall_address_groups(self, name=None):
        return self.list_all("/v1/firewall/address-groups", "groups", {"name": name})

    def get_firewall_address_group(self, group_id):
        return self.get("/v1/firewall/address-groups/" + path_escape(group_id))

    def create_firewall_address_group(self, name, prefixes):
        out = self.request("POST", "/v1/firewall/address-groups", body={"group": {"name": name, "prefixes": prefixes}}).get("group")
        if out and out.get("id"):
            return out
        return self.find_by_name(self.list_firewall_address_groups(name), name)

    def update_firewall_address_group(self, group_id, name, prefixes):
        self.request("PATCH", "/v1/firewall/address-groups/" + path_escape(group_id), body={"group": {"name": name, "prefixes": prefixes}})
        return self.get_firewall_address_group(group_id)

    def delete_firewall_address_group(self, group_id):
        self.request("DELETE", "/v1/firewall/address-groups/" + path_escape(group_id))

    def list_firewall_rulesets(self, name=None, attachment=None):
        return self.list_all("/v1/firewall/rulesets", "rulesets", {"name": name, "filterAttachment": attachment})

    def get_firewall_ruleset(self, ruleset_id):
        return self.get("/v1/firewall/rulesets/" + path_escape(ruleset_id))

    def create_firewall_ruleset(self, name):
        out = self.request("POST", "/v1/firewall/rulesets", body={"ruleset": {"name": name}}).get("ruleset")
        if out and out.get("id"):
            return out
        return self.find_by_name(self.list_firewall_rulesets(name), name)

    def update_firewall_ruleset(self, ruleset_id, name):
        self.request("PATCH", "/v1/firewall/rulesets/" + path_escape(ruleset_id), body={"ruleset": {"name": name}})
        return self.get_firewall_ruleset(ruleset_id)

    def delete_firewall_ruleset(self, ruleset_id, force=False):
        self.request("DELETE", "/v1/firewall/rulesets/" + path_escape(ruleset_id), query={"force": "true"} if force else None)

    def list_firewall_rules(self, ruleset_id):
        rules = self.list_all("/v1/firewall/rulesets/" + path_escape(ruleset_id) + "/rules", "rules")
        return sorted(rules, key=lambda r: int(r.get("position") or 0))

    def create_firewall_rule(self, ruleset_id, rule):
        return self.request("POST", "/v1/firewall/rulesets/" + path_escape(ruleset_id) + "/rules", body={"rule": rule}).get("rule")

    def update_firewall_rule(self, rule_id, rule):
        return self.request("PATCH", "/v1/firewall/rules/" + path_escape(rule_id), body={"rule": rule})

    def move_firewall_rule(self, rule_id, target_id, position="FIREWALL_RULE_POSITION_BEFORE"):
        return self.request("POST", "/v1/firewall/rules/" + path_escape(rule_id) + "/move",
                            body={"targetRuleId": target_id, "position": position})

    def delete_firewall_rule(self, rule_id):
        self.request("DELETE", "/v1/firewall/rules/" + path_escape(rule_id))

    @staticmethod
    def find_by_name(items, name):
        for item in items or []:
            if item.get("name") == name:
                return item
        return None

    # -- virtual machines ----------------------------------------------------------

    @staticmethod
    def vm_path(vm_id):
        return "/v1/virtual-machines/" + path_escape(vm_id)

    def list_virtual_machines(self):
        return self.list_all("/v1/virtual-machines", "virtualMachines")

    def get_virtual_machine(self, vm_id):
        vm = self.get(self.vm_path(vm_id))
        if not vm or not vm.get("id"):
            raise NodeRingsError(404, CODE_NOT_FOUND, "virtual machine %s not found" % vm_id)
        return vm

    def create_virtual_machine(self, body):
        # Never retried blindly: the caller handles ambiguous failures.
        return self.request("POST", "/v1/virtual-machines", body=body, retries=0).get("virtualMachine")

    def update_virtual_machine_tags(self, vm_id, add=None, remove=None):
        return self.request("PATCH", self.vm_path(vm_id), body={"addTags": add or [], "removeTags": remove or []})

    def delete_virtual_machine(self, vm_id):
        self.request("DELETE", self.vm_path(vm_id))

    def vm_action(self, vm_id, action, body=None):
        return self.request("POST", self.vm_path(vm_id) + ":" + action, body=body if body is not None else {})

    def list_vm_tags(self):
        return self.get("/v1/virtual-machines/tags").get("tags") or []

    def list_snapshots(self, vm_id):
        return self.list_all(self.vm_path(vm_id) + "/snapshots", "snapshots")

    def create_snapshot(self, vm_id, description):
        return self.request("POST", self.vm_path(vm_id) + "/snapshots", body={"description": description}, retries=0).get("snapshot")

    def get_snapshot(self, vm_id, snapshot_id):
        return self.get(self.vm_path(vm_id) + "/snapshots/" + path_escape(snapshot_id)).get("snapshot")

    def delete_snapshot(self, vm_id, snapshot_id):
        self.request("DELETE", self.vm_path(vm_id) + "/snapshots/" + path_escape(snapshot_id))

    def list_backups(self, vm_id):
        return self.list_all(self.vm_path(vm_id) + "/backups", "backups")

    # -- marketplace & catalog -----------------------------------------------------

    def list_marketplace_regions(self, asset_type=None):
        return self.get("/v1/marketplace/regions", {"filterAssetType": asset_type}).get("regions") or []

    def list_available_plans(self, country=None, city=None, billing_type=None, asset_type=None):
        return self.get("/v1/marketplace/plans", {
            "filterCountry": country, "filterCity": city, "filterBillingType": billing_type, "filterAssetType": asset_type,
        }).get("plans") or []

    def get_marketplace_plan(self, plan_id):
        return self.get("/v1/marketplace/plans/" + path_escape(plan_id))

    def list_providers(self, plan_code, country, city, billing_type=None, ipv6_only=False):
        q = {"page": "0", "pageSize": "-1", "filterPlanCode": plan_code, "filterCountry": country, "filterCity": city,
             "filterBillingType": billing_type}
        if ipv6_only:
            q["filterIpv6AvailableOnly"] = "true"
        return self.get("/v1/marketplace/providers", q).get("providers") or []

    def get_provider(self, provider_id):
        return self.get("/v1/marketplace/providers/" + path_escape(provider_id)).get("provider")

    def list_provider_directory(self, asset_type=None, search=None):
        return self.list_all("/v1/marketplace/provider-directory", "providers", {"filterAssetType": asset_type, "search": search})

    def list_available_addons(self, vm_id=None, provider_id=None, addon_type=None, billing_type=None):
        return self.list_all("/v1/marketplace/addons", "addons", {
            "vmId": vm_id, "filterProviderId": provider_id, "filterAddonType": addon_type, "filterBillingType": billing_type,
        })

    def get_public_storefront(self, slug):
        return self.get("/v1/public/storefronts/" + path_escape(slug)).get("storefront")

    def list_distros(self):
        return self.get("/v1/distros").get("distros") or []

    def list_instant_apps(self, query=None, categories=None, distro=None):
        return self.list_all("/v1/instantapps", "instantApps", {"query": query, "categories": categories or None, "distro": distro})

    def get_instant_app_by_slug(self, slug):
        return self.get("/v1/instantapps/slug/" + path_escape(slug))

    # -- billing -------------------------------------------------------------------

    def get_credit_balance(self):
        return self.get("/v1/credits/balance")

    def list_subscriptions(self, only_active=False):
        return self.list_paged("/v1/subscriptions", "subscriptions", {"onlyActive": "true" if only_active else None})

    def get_entitlements(self):
        return self.get("/v1/subscriptions:status").get("rules") or []

    # -- IAM -----------------------------------------------------------------------

    def list_permissions(self, name_filter=None):
        return self.list_all("/v1/permissions", "permissions", {"filterName": name_filter})

    def list_roles(self):
        return self.list_all("/v1/roles", "roles")

    def create_role(self, name, description, permission_ids):
        return self.request("POST", "/v1/roles", body={"name": name, "description": description or "", "permissions": permission_ids or []}).get("role")

    def update_role(self, role_id, name, description):
        return self.request("PATCH", "/v1/roles/" + path_escape(role_id), body={"name": name, "description": description or ""}).get("role")

    def delete_role(self, role_id):
        self.request("DELETE", "/v1/roles/" + path_escape(role_id))

    def assign_permissions(self, role_id, permission_ids):
        self.request("POST", "/v1/permissions/assign-to-role", body={"roleId": role_id, "permissionIds": permission_ids})

    def remove_permissions(self, role_id, permission_ids):
        self.request("DELETE", "/v1/permissions/remove-from-role", query={"roleId": role_id, "permissionIds": permission_ids})

    def replace_role(self, principal_type, principal_id, role_id):
        path, field = {
            "user": ("/v1/roles/replace-for-user", "userId"),
            "group": ("/v1/roles/replace-for-group", "groupId"),
            "service_account": ("/v1/roles/replace-for-service-account", "serviceAccountId"),
        }[principal_type]
        self.request("PUT", path, body={field: principal_id, "roleId": role_id})

    def list_groups(self):
        return self.list_all("/v1/groups", "groups")

    def get_group(self, group_id):
        return self.get("/v1/groups/" + path_escape(group_id)).get("group")

    def create_group(self, name, description):
        return self.request("POST", "/v1/groups", body={"name": name, "description": description or ""}).get("group")

    def update_group(self, group_id, name, description):
        return self.request("PATCH", "/v1/groups/" + path_escape(group_id), body={"name": name, "description": description or ""}).get("group")

    def delete_group(self, group_id):
        self.request("DELETE", "/v1/groups/" + path_escape(group_id))

    def add_users_to_group(self, group_id, user_ids):
        self.request("POST", "/v1/groups/add-user", body={"groupId": group_id, "userIds": user_ids})

    def remove_users_from_group(self, group_id, user_ids):
        self.request("DELETE", "/v1/groups/remove-user", query={"groupId": group_id, "userIds": user_ids})

    def add_service_accounts_to_group(self, group_id, ids):
        self.request("POST", "/v1/groups/add-service-account", body={"groupId": group_id, "serviceAccountIds": ids})

    def remove_service_accounts_from_group(self, group_id, ids):
        self.request("DELETE", "/v1/groups/remove-service-account", query={"groupId": group_id, "serviceAccountIds": ids})

    def list_users(self):
        return self.list_all("/v1/users", "users")

    def list_service_accounts(self):
        return self.list_all("/v1/service-accounts", "serviceAccounts")

    def list_secrets(self):
        return self.list_all("/v1/secrets", "secrets")

    def create_secret(self, key, value):
        return self.request("POST", "/v1/secrets", body={"key": key, "value": value}).get("secret")

    def get_secret(self, secret_id):
        return self.get("/v1/secrets/" + path_escape(secret_id)).get("secret")

    def update_secret(self, secret_id, value):
        self.request("PATCH", "/v1/secrets/" + path_escape(secret_id), body={"value": value})

    def delete_secret(self, secret_id):
        self.request("DELETE", "/v1/secrets/" + path_escape(secret_id))

    def list_environment_variables(self):
        return self.list_all("/v1/environment-variables", "environmentVariables")

    def create_environment_variable(self, key, value):
        return self.request("POST", "/v1/environment-variables", body={"key": key, "value": value}).get("environmentVariable")

    def get_environment_variable(self, env_id):
        return self.get("/v1/environment-variables/" + path_escape(env_id)).get("environmentVariable")

    def update_environment_variable(self, env_id, value):
        self.request("PATCH", "/v1/environment-variables/" + path_escape(env_id), body={"value": value})

    def delete_environment_variable(self, env_id):
        self.request("DELETE", "/v1/environment-variables/" + path_escape(env_id))

    # -- game servers --------------------------------------------------------------

    @staticmethod
    def gs_path(gs_id, *rest):
        return "/v1/game-servers/" + path_escape(gs_id) + "".join(rest)

    def list_game_servers(self):
        return self.list_all("/v1/game-servers", "gameServers")

    def get_game_server(self, gs_id):
        out = self.get(self.gs_path(gs_id)) or {}
        out = out.get("gameServer", out)
        if not out.get("id"):
            raise NodeRingsError(404, CODE_NOT_FOUND, "game server %s not found" % gs_id)
        return out

    def create_game_server(self, body):
        out = self.request("POST", "/v1/game-servers", body=body, retries=0)
        return out.get("gameServer", out)

    def delete_game_server(self, gs_id):
        self.request("DELETE", self.gs_path(gs_id))

    def rename_game_server(self, gs_id, name):
        self.request("POST", self.gs_path(gs_id, ":rename"), body={"name": name})

    def power_game_server(self, gs_id, signal):
        self.request("POST", self.gs_path(gs_id, ":power"), body={"signal": signal})

    def get_game_server_resources(self, gs_id):
        out = self.get(self.gs_path(gs_id, "/resources"))
        return out.get("resources", out)

    def get_game_server_startup(self, gs_id):
        out = self.get(self.gs_path(gs_id, "/startup"))
        return out.get("startup", out)

    def update_game_server_startup_variable(self, gs_id, key, value):
        self.request("PUT", self.gs_path(gs_id, "/startup"), body={"key": key, "value": value})

    def change_game_server_game(self, gs_id, template_id, environment=None, accept_eula=False):
        body = {"templateId": template_id, "acceptEula": accept_eula}
        if environment:
            body["environment"] = environment
        self.request("POST", self.gs_path(gs_id, ":changeGame"), body=body)

    def update_game_server_docker_image(self, gs_id, image):
        self.request("PUT", self.gs_path(gs_id, "/docker-image"), body={"dockerImage": image})

    def list_order_games(self, plan_id):
        return self.get("/v1/game-servers:order-games", {"planId": plan_id}).get("games") or []

    def list_game_server_backups(self, gs_id):
        return self.get(self.gs_path(gs_id, "/backups")).get("backups") or []

    def create_game_server_backup(self, gs_id, name):
        out = self.request("POST", self.gs_path(gs_id, "/backups"), body={"name": name}, retries=0)
        return out.get("backup", out)

    def toggle_game_server_backup_lock(self, gs_id, backup_id):
        self.request("POST", self.gs_path(gs_id, "/backups/", path_escape(backup_id), ":lock"), body={})

    def delete_game_server_backup(self, gs_id, backup_id):
        self.request("DELETE", self.gs_path(gs_id, "/backups/", path_escape(backup_id)))

    def list_game_server_databases(self, gs_id):
        return self.get(self.gs_path(gs_id, "/databases")).get("databases") or []

    def create_game_server_database(self, gs_id, name, remote):
        out = self.request("POST", self.gs_path(gs_id, "/databases"), body={"database": name, "remote": remote})
        return out.get("database", out)

    def rotate_game_server_database_password(self, gs_id, database_id):
        out = self.request("POST", self.gs_path(gs_id, "/databases/", path_escape(database_id), ":rotate"), body={})
        return out.get("database", out)

    def delete_game_server_database(self, gs_id, database_id):
        self.request("DELETE", self.gs_path(gs_id, "/databases/", path_escape(database_id)))


class Waiter(object):
    """Polls with a growing interval until a check reports done or a timeout passes."""

    def __init__(self, timeout, interval=2.0, max_interval=15.0, sleep=time.sleep, clock=time.time):
        self.deadline = clock() + timeout
        self.interval = interval
        self.max_interval = max_interval
        self._sleep = sleep
        self._clock = clock

    def wait(self, what, check):
        delay = self.interval
        while True:
            done, value = check()
            if done:
                return value
            if self._clock() + delay > self.deadline:
                raise TimeoutError_("timed out waiting for %s; raise wait_timeout if this keeps happening" % what)
            self._sleep(delay)
            delay = min(delay * 1.5, self.max_interval)

    def retry_busy(self, func):
        """Run func until the VM stops reporting 'operation in progress'."""
        last = [None]

        def check():
            try:
                return True, func()
            except NodeRingsError as e:
                if is_busy(e):
                    last[0] = e
                    return False, None
                raise

        try:
            return self.wait("the virtual machine to finish its current operation", check)
        except TimeoutError_ as e:
            raise TimeoutError_("%s (last error: %s)" % (e, last[0]))


class TimeoutError_(Exception):
    """Raised when a wait times out (named to avoid shadowing the Python 3 builtin)."""


class NodeRingsModule(object):
    """Base helper: builds the client from module params and formats failures."""

    def __init__(self, module):
        self.module = module
        p = module.params
        try:
            self.client = NodeRingsClient(
                api_url=p.get("api_url"),
                token=p.get("api_token"),
                organization_id=p.get("organization_id"),
                timeout=p.get("api_timeout") or 60,
                retries=p.get("api_retries") if p.get("api_retries") is not None else 5,
                validate_certs=p.get("validate_certs", True),
            )
        except ValueError as e:
            module.fail_json(msg=to_native(e))
        self.changed = False
        self.diff = {"before": {}, "after": {}}

    def fail(self, what, err):
        kwargs = {}
        if isinstance(err, NodeRingsError):
            kwargs["status"] = err.status
            kwargs["api_code"] = err.code
        self.module.fail_json(msg="%s: %s" % (what, to_native(err)), **kwargs)

    def call(self, what, func, *args, **kwargs):
        """Run an API call and fail the module with context if it raises."""
        try:
            return func(*args, **kwargs)
        except (NodeRingsError, URLError, IOError, OSError, TimeoutError_, ValueError) as e:
            self.fail(what, e)


# Values under these keys are free-form maps (user data); their keys are kept as-is.
OPAQUE_KEYS = frozenset(["metadata", "continents", "countries", "regions", "environment", "instantAppVariables", "labels"])


def snake(value):
    """Convert API camelCase keys to snake_case, recursively."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in OPAQUE_KEYS and isinstance(v, dict):
                out[_snake_key(k)] = v
            else:
                out[_snake_key(k)] = snake(v)
        return out
    if isinstance(value, list):
        return [snake(v) for v in value]
    return value


def pick(obj, *keys):
    """Return only the given API keys of obj, converted to snake_case."""
    obj = obj or {}
    return snake(dict((k, obj.get(k)) for k in keys if k in obj))


def _snake_key(key):
    out = []
    for i, ch in enumerate(key):
        if ch.isupper():
            if i and (not key[i - 1].isupper() or (i + 1 < len(key) and key[i + 1].islower())):
                out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out).lstrip("@")


def int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def resolve_role(nr, ref):
    """Find a role by ID or name (case-insensitive)."""
    roles = nr.call("listing roles", nr.client.list_roles)
    for r in roles:
        if r.get("id") == ref:
            return r
    matches = [r for r in roles if (r.get("name") or "").lower() == (ref or "").lower()]
    if not matches:
        nr.module.fail_json(msg="role %s does not exist; available: %s" % (ref, ", ".join(sorted(r.get("name") or "" for r in roles))))
    return matches[0]


def resolve_permissions(nr, refs):
    """Map permission method names (for example ListVirtualMachines) or IDs to IDs."""
    perms = nr.call("listing permissions", nr.client.list_permissions)
    by_id = dict((x.get("id"), x) for x in perms)
    by_name = {}
    for x in perms:
        by_name.setdefault(x.get("methodName"), []).append(x)
    out = []
    for ref in refs or []:
        if ref in by_id:
            out.append(ref)
        elif ref in by_name:
            out.extend(x.get("id") for x in by_name[ref])
        else:
            nr.module.fail_json(msg="permission %s does not exist; list them with noderings.cloud.iam_info" % ref)
    return sorted(set(out)), by_id
