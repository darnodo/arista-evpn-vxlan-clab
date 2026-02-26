"""Async Infrahub client for Arista EVPN-VXLAN fabric intent retrieval."""

import time
from typing import Any

from infrahub_sdk import Config, InfrahubClient

from .exceptions import InfrahubNotFoundError, InfrahubQueryError
from .models import (
    BgpPeerGroupIntent,
    BgpRouterConfigIntent,
    BgpSessionIntent,
    DeviceIntent,
    EvpnInstanceIntent,
    MlagDomainIntent,
    MlagPeerConfigIntent,
    VlanIntent,
    VniIntent,  # noqa: F401 — re-exported for convenience
    VrfIntent,
    VtepIntent,
)

_CACHE_TTL_SECONDS = 60


class FabricInfrahubClient:
    """Async client that wraps the Infrahub SDK to fetch fabric intent data.

    All public methods return immutable Pydantic models. Results are cached
    in-memory with a TTL of ``_CACHE_TTL_SECONDS`` seconds to avoid redundant
    queries during a single reconciliation pass.

    Example::

        async with FabricInfrahubClient(url="http://infrahub:8080", api_token="xxx") as client:
            device = await client.get_device("leaf1")
    """

    def __init__(self, url: str, api_token: str, branch: str = "main") -> None:
        """Initialise the client.

        Args:
            url: Base URL of the Infrahub server (e.g. ``http://infrahub:8080``).
            api_token: API token used for authentication.
            branch: Infrahub branch to query (default: ``"main"``).
        """
        config = Config(address=url, api_token=api_token, default_branch=branch)
        self._sdk = InfrahubClient(config=config)
        self._branch = branch
        self._cache: dict[str, tuple[Any, float]] = {}

    # ------------------------------------------------------------------
    # Async context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "FabricInfrahubClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Any | None:
        """Return cached value for *key* if still within TTL, else ``None``."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > _CACHE_TTL_SECONDS:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        """Store *value* in the cache under *key* with current timestamp."""
        self._cache[key] = (value, time.monotonic())

    def _opt_value(self, node: Any, attr: str) -> Any | None:
        """Safely read ``node.<attr>.value``, returning ``None`` if missing."""
        try:
            attr_obj = getattr(node, attr, None)
            if attr_obj is None:
                return None
            return attr_obj.value
        except AttributeError:
            return None

    async def _fetch_node(self, kind: str, **filters: Any) -> Any:
        """Fetch a single node; raise :exc:`InfrahubNotFoundError` if absent.

        Args:
            kind: Infrahub node kind (e.g. ``"InfraDevice"``).
            **filters: Keyword arguments forwarded to :meth:`InfrahubClient.get`.

        Returns:
            The SDK node object.

        Raises:
            InfrahubNotFoundError: When no node matches the filters.
            InfrahubQueryError: On SDK/network error.
        """
        try:
            node = await self._sdk.get(kind=kind, branch=self._branch, **filters)
        except Exception as exc:
            msg = str(exc).lower()
            if "not found" in msg or "does not exist" in msg or "nodnotfound" in msg.replace(" ", ""):
                raise InfrahubNotFoundError(
                    f"{kind} with filters {filters} not found"
                ) from exc
            raise InfrahubQueryError(f"Query failed for {kind} with {filters}: {exc}") from exc

        if node is None:
            raise InfrahubNotFoundError(f"{kind} with filters {filters} not found")
        return node

    async def _fetch_all(self, kind: str, **filters: Any) -> list[Any]:
        """Fetch all nodes of *kind* matching optional *filters*.

        Args:
            kind: Infrahub node kind.
            **filters: Optional filter keyword arguments.

        Returns:
            List of SDK node objects (may be empty).

        Raises:
            InfrahubQueryError: On SDK/network error.
        """
        try:
            if filters:
                return await self._sdk.filters(kind=kind, branch=self._branch, **filters)
            return await self._sdk.all(kind=kind, branch=self._branch)
        except Exception as exc:
            raise InfrahubQueryError(f"Query failed for {kind}: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_device(self, name: str) -> DeviceIntent:
        """Fetch a device and its core relationships by name.

        Args:
            name: Device name as stored in Infrahub (e.g. ``"leaf1"``).

        Returns:
            :class:`DeviceIntent` populated from Infrahub.

        Raises:
            InfrahubNotFoundError: When no device with *name* exists.
            InfrahubQueryError: On query failure.
        """
        cache_key = f"device:{name}"
        if cached := self._cache_get(cache_key):
            return cached

        node = await self._fetch_node("InfraDevice", name__value=name)

        # Resolve optional one-cardinality relationships
        platform_name: str | None = None
        if node.platform and node.platform.initialized:
            await node.platform.fetch()
            platform_name = self._opt_value(node.platform.peer, "name")

        site_name: str | None = None
        if node.site and node.site.initialized:
            await node.site.fetch()
            site_name = self._opt_value(node.site.peer, "name")

        asn_value: int | None = None
        if node.asn and node.asn.initialized:
            await node.asn.fetch()
            asn_value = self._opt_value(node.asn.peer, "asn")

        result = DeviceIntent(
            name=node.name.value,
            role=node.role.value,
            status=node.status.value,
            platform=platform_name,
            site=site_name,
            asn=asn_value,
        )
        self._cache_set(cache_key, result)
        return result

    async def get_device_vlans(self, device_name: str) -> list[VlanIntent]:
        """Fetch VLANs associated with a device via its VTEP vlan-vni mappings.

        Falls back to VLANs linked through SVI interfaces when no VTEP exists.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            List of :class:`VlanIntent` objects (may be empty).

        Raises:
            InfrahubNotFoundError: When the device does not exist.
            InfrahubQueryError: On query failure.
        """
        cache_key = f"device_vlans:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        # Ensure device exists
        device_node = await self._fetch_node("InfraDevice", name__value=device_name)

        vlan_intents: list[VlanIntent] = []
        seen_vlan_ids: set[int] = set()

        # Try via VTEP → VlanVniMapping → VLAN
        try:
            vtep_nodes = await self._fetch_all(
                "InfraVTEP", device__name__value=device_name
            )
        except InfrahubQueryError:
            vtep_nodes = []

        for vtep in vtep_nodes:
            if not (vtep.vlan_vni_mappings and vtep.vlan_vni_mappings.initialized):
                continue
            for mapping_rel in vtep.vlan_vni_mappings.peers:
                mapping = mapping_rel.peer
                if not (mapping.vlan and mapping.vlan.initialized):
                    continue
                await mapping.vlan.fetch()
                vlan_node = mapping.vlan.peer
                if vlan_node is None:
                    continue
                vlan_id: int = vlan_node.vlan_id.value
                if vlan_id in seen_vlan_ids:
                    continue
                seen_vlan_ids.add(vlan_id)

                vni_val: int | None = None
                if vlan_node.vni and vlan_node.vni.initialized:
                    await vlan_node.vni.fetch()
                    if vlan_node.vni.peer:
                        vni_val = vlan_node.vni.peer.vni.value

                vlan_intents.append(
                    VlanIntent(
                        vlan_id=vlan_id,
                        name=vlan_node.name.value,
                        status=vlan_node.status.value,
                        vlan_type=vlan_node.vlan_type.value,
                        vni=vni_val,
                        stp_enabled=bool(self._opt_value(vlan_node, "stp_enabled")),
                    )
                )

        # Fallback: VLANs via SVI interfaces on the device
        if not vlan_intents:
            interfaces = await self._fetch_all(
                "InfraInterfaceVlan", device__name__value=device_name
            )
            for intf in interfaces:
                if not (intf.vlan and intf.vlan.initialized):
                    continue
                await intf.vlan.fetch()
                vlan_node = intf.vlan.peer
                if vlan_node is None:
                    continue
                vlan_id = vlan_node.vlan_id.value
                if vlan_id in seen_vlan_ids:
                    continue
                seen_vlan_ids.add(vlan_id)

                vni_val = None
                if vlan_node.vni and vlan_node.vni.initialized:
                    await vlan_node.vni.fetch()
                    if vlan_node.vni.peer:
                        vni_val = vlan_node.vni.peer.vni.value

                vlan_intents.append(
                    VlanIntent(
                        vlan_id=vlan_id,
                        name=vlan_node.name.value,
                        status=vlan_node.status.value,
                        vlan_type=vlan_node.vlan_type.value,
                        vni=vni_val,
                        stp_enabled=bool(self._opt_value(vlan_node, "stp_enabled")),
                    )
                )

        # Suppress unused variable warning — device_node used for existence check
        _ = device_node

        self._cache_set(cache_key, vlan_intents)
        return vlan_intents

    async def get_device_bgp_config(self, device_name: str) -> BgpRouterConfigIntent:
        """Fetch the BGP router config for a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            :class:`BgpRouterConfigIntent` for the device.

        Raises:
            InfrahubNotFoundError: When no BGP config exists for the device.
            InfrahubQueryError: On query failure.
        """
        cache_key = f"bgp_config:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        node = await self._fetch_node(
            "InfraBGPRouterConfig", device__name__value=device_name
        )

        local_asn: int = 0
        if node.local_asn and node.local_asn.initialized:
            await node.local_asn.fetch()
            if node.local_asn.peer:
                local_asn = node.local_asn.peer.asn.value

        result = BgpRouterConfigIntent(
            router_id=node.router_id.value,
            local_asn=local_asn,
            default_ipv4_unicast=bool(self._opt_value(node, "default_ipv4_unicast")),
            ecmp_max_paths=int(self._opt_value(node, "ecmp_max_paths") or 1),
        )
        self._cache_set(cache_key, result)
        return result

    async def get_device_bgp_peer_groups(self, device_name: str) -> list[BgpPeerGroupIntent]:
        """Fetch all BGP peer groups configured on a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            List of :class:`BgpPeerGroupIntent` objects.

        Raises:
            InfrahubNotFoundError: When no BGP config exists for the device.
            InfrahubQueryError: On query failure.
        """
        cache_key = f"bgp_peer_groups:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        bgp_node = await self._fetch_node(
            "InfraBGPRouterConfig", device__name__value=device_name
        )

        results: list[BgpPeerGroupIntent] = []
        if not (bgp_node.peer_groups and bgp_node.peer_groups.initialized):
            self._cache_set(cache_key, results)
            return results

        for pg_rel in bgp_node.peer_groups.peers:
            pg = pg_rel.peer

            remote_asn: int | None = None
            if pg.remote_asn and pg.remote_asn.initialized:
                await pg.remote_asn.fetch()
                if pg.remote_asn.peer:
                    remote_asn = pg.remote_asn.peer.asn.value

            results.append(
                BgpPeerGroupIntent(
                    name=pg.name.value,
                    peer_group_type=pg.peer_group_type.value,
                    remote_asn=remote_asn,
                    update_source=self._opt_value(pg, "update_source"),
                    send_community=bool(self._opt_value(pg, "send_community")),
                    ebgp_multihop=self._opt_value(pg, "ebgp_multihop"),
                    next_hop_unchanged=bool(self._opt_value(pg, "next_hop_unchanged")),
                )
            )

        self._cache_set(cache_key, results)
        return results

    async def get_device_bgp_sessions(self, device_name: str) -> list[BgpSessionIntent]:
        """Fetch all BGP sessions configured on a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            List of :class:`BgpSessionIntent` objects.

        Raises:
            InfrahubNotFoundError: When no BGP config exists for the device.
            InfrahubQueryError: On query failure.
        """
        cache_key = f"bgp_sessions:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        bgp_node = await self._fetch_node(
            "InfraBGPRouterConfig", device__name__value=device_name
        )

        results: list[BgpSessionIntent] = []
        if not (bgp_node.sessions and bgp_node.sessions.initialized):
            self._cache_set(cache_key, results)
            return results

        for sess_rel in bgp_node.sessions.peers:
            sess = sess_rel.peer

            peer_group_name: str | None = None
            if sess.peer_group and sess.peer_group.initialized:
                await sess.peer_group.fetch()
                if sess.peer_group.peer:
                    peer_group_name = sess.peer_group.peer.name.value

            remote_asn: int | None = None
            if sess.remote_asn and sess.remote_asn.initialized:
                await sess.remote_asn.fetch()
                if sess.remote_asn.peer:
                    remote_asn = sess.remote_asn.peer.asn.value

            results.append(
                BgpSessionIntent(
                    peer_address=sess.peer_address.value,
                    description=self._opt_value(sess, "description"),
                    enabled=bool(self._opt_value(sess, "enabled")),
                    peer_group=peer_group_name,
                    remote_asn=remote_asn,
                )
            )

        self._cache_set(cache_key, results)
        return results

    async def get_device_vrfs(self, device_name: str) -> list[VrfIntent]:
        """Fetch all VRFs assigned to a device via VRFDeviceAssignment.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            List of :class:`VrfIntent` objects (may be empty).

        Raises:
            InfrahubQueryError: On query failure.
        """
        cache_key = f"device_vrfs:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        assignments = await self._fetch_all(
            "InfraVRFDeviceAssignment", device__name__value=device_name
        )

        results: list[VrfIntent] = []
        for assignment in assignments:
            if not (assignment.vrf and assignment.vrf.initialized):
                continue
            await assignment.vrf.fetch()
            vrf_node = assignment.vrf.peer
            if vrf_node is None:
                continue

            l3vni: int | None = None
            if vrf_node.l3vni and vrf_node.l3vni.initialized:
                await vrf_node.l3vni.fetch()
                if vrf_node.l3vni.peer:
                    l3vni = vrf_node.l3vni.peer.vni.value

            import_targets: list[str] = []
            if vrf_node.import_targets and vrf_node.import_targets.initialized:
                for rt_rel in vrf_node.import_targets.peers:
                    import_targets.append(rt_rel.peer.target.value)

            export_targets: list[str] = []
            if vrf_node.export_targets and vrf_node.export_targets.initialized:
                for rt_rel in vrf_node.export_targets.peers:
                    export_targets.append(rt_rel.peer.target.value)

            results.append(
                VrfIntent(
                    name=vrf_node.name.value,
                    route_distinguisher=self._opt_value(vrf_node, "route_distinguisher"),
                    vrf_id=self._opt_value(vrf_node, "vrf_id"),
                    l3vni=l3vni,
                    import_targets=import_targets,
                    export_targets=export_targets,
                )
            )

        self._cache_set(cache_key, results)
        return results

    async def get_device_vtep(self, device_name: str) -> VtepIntent | None:
        """Fetch the VTEP configuration for a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            :class:`VtepIntent` if a VTEP exists for the device, else ``None``.

        Raises:
            InfrahubQueryError: On query failure.
        """
        cache_key = f"device_vtep:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        vtep_nodes = await self._fetch_all(
            "InfraVTEP", device__name__value=device_name
        )
        if not vtep_nodes:
            self._cache_set(cache_key, None)
            return None

        vtep = vtep_nodes[0]
        mappings: list[tuple[int, int]] = []

        if vtep.vlan_vni_mappings and vtep.vlan_vni_mappings.initialized:
            for mapping_rel in vtep.vlan_vni_mappings.peers:
                mapping = mapping_rel.peer
                vlan_id: int | None = None
                vni_id: int | None = None

                if mapping.vlan and mapping.vlan.initialized:
                    await mapping.vlan.fetch()
                    if mapping.vlan.peer:
                        vlan_id = mapping.vlan.peer.vlan_id.value

                if mapping.vni and mapping.vni.initialized:
                    await mapping.vni.fetch()
                    if mapping.vni.peer:
                        vni_id = mapping.vni.peer.vni.value

                if vlan_id is not None and vni_id is not None:
                    mappings.append((vlan_id, vni_id))

        result = VtepIntent(
            source_address=vtep.source_address.value,
            udp_port=int(self._opt_value(vtep, "udp_port") or 4789),
            learn_restrict=bool(self._opt_value(vtep, "learn_restrict")),
            vlan_vni_mappings=mappings,
        )
        self._cache_set(cache_key, result)
        return result

    async def get_device_evpn_instances(self, device_name: str) -> list[EvpnInstanceIntent]:
        """Fetch all EVPN instances for a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            List of :class:`EvpnInstanceIntent` objects.

        Raises:
            InfrahubQueryError: On query failure.
        """
        cache_key = f"device_evpn:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        nodes = await self._fetch_all(
            "InfraEVPNInstance", device__name__value=device_name
        )

        results: list[EvpnInstanceIntent] = []
        for node in nodes:
            vlan_id: int = 0
            if node.vlan and node.vlan.initialized:
                await node.vlan.fetch()
                if node.vlan.peer:
                    vlan_id = node.vlan.peer.vlan_id.value

            results.append(
                EvpnInstanceIntent(
                    route_distinguisher=node.route_distinguisher.value,
                    route_target_import=node.route_target_import.value,
                    route_target_export=node.route_target_export.value,
                    redistribute_learned=bool(
                        self._opt_value(node, "redistribute_learned")
                    ),
                    vlan_id=vlan_id,
                )
            )

        self._cache_set(cache_key, results)
        return results

    async def get_mlag_domain(self, device_name: str) -> MlagDomainIntent | None:
        """Fetch the MLAG domain that includes the given device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            :class:`MlagDomainIntent` if the device belongs to an MLAG domain,
            else ``None``.

        Raises:
            InfrahubQueryError: On query failure.
        """
        cache_key = f"mlag_domain:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        domains = await self._fetch_all("InfraMlagDomain")
        for domain in domains:
            if not (domain.devices and domain.devices.initialized):
                continue
            device_names: list[str] = []
            for dev_rel in domain.devices.peers:
                device_names.append(dev_rel.peer.name.value)

            if device_name not in device_names:
                continue

            peer_vlan: str | None = None
            if domain.peer_vlan and domain.peer_vlan.initialized:
                await domain.peer_vlan.fetch()
                if domain.peer_vlan.peer:
                    peer_vlan = str(domain.peer_vlan.peer.vlan_id.value)

            result = MlagDomainIntent(
                domain_id=str(domain.domain_id.value),
                virtual_mac=domain.virtual_mac.value,
                heartbeat_vrf=self._opt_value(domain, "heartbeat_vrf") or "",
                dual_primary_detection=bool(
                    self._opt_value(domain, "dual_primary_detection")
                ),
                dual_primary_delay=int(self._opt_value(domain, "dual_primary_delay") or 0),
                dual_primary_action=self._opt_value(domain, "dual_primary_action") or "",
                peer_devices=device_names,
            )
            self._cache_set(cache_key, result)
            return result

        self._cache_set(cache_key, None)
        return None

    async def get_mlag_peer_config(self, device_name: str) -> MlagPeerConfigIntent | None:
        """Fetch the MLAG peer config for a device.

        Args:
            device_name: Device name as stored in Infrahub.

        Returns:
            :class:`MlagPeerConfigIntent` if a config exists, else ``None``.

        Raises:
            InfrahubQueryError: On query failure.
        """
        cache_key = f"mlag_peer_config:{device_name}"
        if cached := self._cache_get(cache_key):
            return cached

        configs = await self._fetch_all(
            "InfraMlagPeerConfig", device__name__value=device_name
        )
        if not configs:
            self._cache_set(cache_key, None)
            return None

        cfg = configs[0]

        peer_link_name: str = ""
        if cfg.peer_link and cfg.peer_link.initialized:
            await cfg.peer_link.fetch()
            if cfg.peer_link.peer:
                peer_link_name = cfg.peer_link.peer.name.value

        result = MlagPeerConfigIntent(
            local_interface_ip=cfg.local_interface_ip.value,
            peer_address=cfg.peer_address.value,
            heartbeat_peer_ip=self._opt_value(cfg, "heartbeat_peer_ip") or "",
            peer_link=peer_link_name,
        )
        self._cache_set(cache_key, result)
        return result
