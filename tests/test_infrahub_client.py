"""Unit tests for FabricInfrahubClient — all Infrahub SDK calls are mocked."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub_client import (
    FabricInfrahubClient,
    InfrahubNotFoundError,
    InfrahubQueryError,
)
from infrahub_client.models import (
    BgpPeerGroupIntent,
    BgpRouterConfigIntent,
    BgpSessionIntent,
    DeviceIntent,
    EvpnInstanceIntent,
    MlagDomainIntent,
    MlagPeerConfigIntent,
    VlanIntent,
    VrfIntent,
    VtepIntent,
)


# ---------------------------------------------------------------------------
# Helpers to build mock SDK node objects
# ---------------------------------------------------------------------------


def _attr(value):
    """Return a simple attribute mock with ``.value`` set."""
    m = MagicMock()
    m.value = value
    return m


def _rel_one(peer_node, initialized=True):
    """Return a mock for a cardinality-one relationship."""
    m = MagicMock()
    m.initialized = initialized
    m.peer = peer_node
    m.fetch = AsyncMock()
    return m


def _rel_many(peers, initialized=True):
    """Return a mock for a cardinality-many relationship (list of peer wrappers)."""
    m = MagicMock()
    m.initialized = initialized
    peer_wrappers = []
    for p in peers:
        pw = MagicMock()
        pw.peer = p
        peer_wrappers.append(pw)
    m.peers = peer_wrappers
    return m


def _make_device(
    name="leaf1",
    role="leaf",
    status="active",
    platform_name="eos",
    site_name="dc1",
    asn_value=65001,
):
    """Build a mock InfraDevice SDK node."""
    node = MagicMock()
    node.name = _attr(name)
    node.role = _attr(role)
    node.status = _attr(status)

    platform = MagicMock()
    platform.name = _attr(platform_name)
    node.platform = _rel_one(platform)

    site = MagicMock()
    site.name = _attr(site_name)
    node.site = _rel_one(site)

    asn = MagicMock()
    asn.asn = _attr(asn_value)
    node.asn = _rel_one(asn)

    return node


def _make_sdk_client(get_return=None, all_return=None, filters_return=None, get_raises=None):
    """Patch InfrahubClient inside client module and configure return values."""
    mock_sdk = MagicMock()
    if get_raises:
        mock_sdk.get = AsyncMock(side_effect=get_raises)
    else:
        mock_sdk.get = AsyncMock(return_value=get_return)
    mock_sdk.all = AsyncMock(return_value=all_return or [])
    mock_sdk.filters = AsyncMock(return_value=filters_return or [])
    return mock_sdk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """FabricInfrahubClient with a patched InfrahubClient SDK."""
    with patch("infrahub_client.client.InfrahubClient") as MockSdk:
        MockSdk.return_value = MagicMock()
        c = FabricInfrahubClient(url="http://infrahub:8080", api_token="token", branch="main")
        yield c


# ---------------------------------------------------------------------------
# get_device
# ---------------------------------------------------------------------------


class TestGetDevice:
    async def test_returns_device_intent(self, client):
        device_node = _make_device()
        client._sdk.get = AsyncMock(return_value=device_node)

        result = await client.get_device("leaf1")

        assert isinstance(result, DeviceIntent)
        assert result.name == "leaf1"
        assert result.role == "leaf"
        assert result.status == "active"
        assert result.platform == "eos"
        assert result.site == "dc1"
        assert result.asn == 65001

    async def test_not_found_raises_error(self, client):
        client._sdk.get = AsyncMock(side_effect=Exception("not found"))

        with pytest.raises(InfrahubNotFoundError):
            await client.get_device("nonexistent")

    async def test_branch_is_forwarded(self, client):
        client._branch = "proposed"
        device_node = _make_device()
        client._sdk.get = AsyncMock(return_value=device_node)

        await client.get_device("leaf1")

        client._sdk.get.assert_called_once_with(
            kind="InfraDevice", branch="proposed", name__value="leaf1"
        )

    async def test_caching_second_call_skips_sdk(self, client):
        device_node = _make_device()
        client._sdk.get = AsyncMock(return_value=device_node)

        first = await client.get_device("leaf1")
        second = await client.get_device("leaf1")

        assert first == second
        # SDK should only have been called once
        assert client._sdk.get.call_count == 1

    async def test_optional_fields_none_when_uninitialized(self, client):
        node = MagicMock()
        node.name = _attr("spine1")
        node.role = _attr("spine")
        node.status = _attr("active")
        node.platform = _rel_one(None, initialized=False)
        node.site = _rel_one(None, initialized=False)
        node.asn = _rel_one(None, initialized=False)
        client._sdk.get = AsyncMock(return_value=node)

        result = await client.get_device("spine1")

        assert result.platform is None
        assert result.site is None
        assert result.asn is None


# ---------------------------------------------------------------------------
# get_device_bgp_config
# ---------------------------------------------------------------------------


class TestGetDeviceBgpConfig:
    def _make_bgp_node(self, router_id="10.0.0.1", asn=65001, default_ipv4=True, ecmp=4):
        node = MagicMock()
        node.router_id = _attr(router_id)
        node.default_ipv4_unicast = _attr(default_ipv4)
        node.ecmp_max_paths = _attr(ecmp)

        asn_peer = MagicMock()
        asn_peer.asn = _attr(asn)
        node.local_asn = _rel_one(asn_peer)

        return node

    async def test_returns_bgp_config_intent(self, client):
        bgp_node = self._make_bgp_node()
        client._sdk.get = AsyncMock(return_value=bgp_node)

        result = await client.get_device_bgp_config("leaf1")

        assert isinstance(result, BgpRouterConfigIntent)
        assert result.router_id == "10.0.0.1"
        assert result.local_asn == 65001
        assert result.default_ipv4_unicast is True
        assert result.ecmp_max_paths == 4

    async def test_not_found_raises_error(self, client):
        client._sdk.get = AsyncMock(side_effect=Exception("not found"))

        with pytest.raises(InfrahubNotFoundError):
            await client.get_device_bgp_config("leaf1")

    async def test_caching(self, client):
        bgp_node = self._make_bgp_node()
        client._sdk.get = AsyncMock(return_value=bgp_node)

        await client.get_device_bgp_config("leaf1")
        await client.get_device_bgp_config("leaf1")

        assert client._sdk.get.call_count == 1


# ---------------------------------------------------------------------------
# get_device_bgp_peer_groups
# ---------------------------------------------------------------------------


class TestGetDeviceBgpPeerGroups:
    def _make_pg(self, name="UNDERLAY", pg_type="underlay", remote_asn=65000):
        pg = MagicMock()
        pg.name = _attr(name)
        pg.peer_group_type = _attr(pg_type)
        pg.update_source = _attr("Loopback0")
        pg.send_community = _attr(True)
        pg.ebgp_multihop = _attr(None)
        pg.next_hop_unchanged = _attr(False)

        asn_peer = MagicMock()
        asn_peer.asn = _attr(remote_asn)
        pg.remote_asn = _rel_one(asn_peer)

        return pg

    async def test_returns_peer_group_intents(self, client):
        pg = self._make_pg()
        bgp_node = MagicMock()
        bgp_node.peer_groups = _rel_many([pg])
        client._sdk.get = AsyncMock(return_value=bgp_node)

        results = await client.get_device_bgp_peer_groups("leaf1")

        assert len(results) == 1
        assert isinstance(results[0], BgpPeerGroupIntent)
        assert results[0].name == "UNDERLAY"
        assert results[0].peer_group_type == "underlay"
        assert results[0].remote_asn == 65000
        assert results[0].send_community is True

    async def test_empty_when_no_peer_groups(self, client):
        bgp_node = MagicMock()
        bgp_node.peer_groups = _rel_many([], initialized=False)
        client._sdk.get = AsyncMock(return_value=bgp_node)

        results = await client.get_device_bgp_peer_groups("leaf1")

        assert results == []


# ---------------------------------------------------------------------------
# get_device_bgp_sessions
# ---------------------------------------------------------------------------


class TestGetDeviceBgpSessions:
    def _make_session(self, peer_addr="192.168.1.1", enabled=True):
        sess = MagicMock()
        sess.peer_address = _attr(peer_addr)
        sess.description = _attr("peer session")
        sess.enabled = _attr(enabled)

        pg_peer = MagicMock()
        pg_peer.name = _attr("UNDERLAY")
        sess.peer_group = _rel_one(pg_peer)

        asn_peer = MagicMock()
        asn_peer.asn = _attr(65000)
        sess.remote_asn = _rel_one(asn_peer)

        return sess

    async def test_returns_session_intents(self, client):
        sess = self._make_session()
        bgp_node = MagicMock()
        bgp_node.sessions = _rel_many([sess])
        client._sdk.get = AsyncMock(return_value=bgp_node)

        results = await client.get_device_bgp_sessions("leaf1")

        assert len(results) == 1
        assert isinstance(results[0], BgpSessionIntent)
        assert results[0].peer_address == "192.168.1.1"
        assert results[0].enabled is True
        assert results[0].peer_group == "UNDERLAY"
        assert results[0].remote_asn == 65000

    async def test_empty_when_no_sessions(self, client):
        bgp_node = MagicMock()
        bgp_node.sessions = _rel_many([], initialized=False)
        client._sdk.get = AsyncMock(return_value=bgp_node)

        results = await client.get_device_bgp_sessions("leaf1")

        assert results == []


# ---------------------------------------------------------------------------
# get_device_vrfs
# ---------------------------------------------------------------------------


class TestGetDeviceVrfs:
    def _make_assignment(self, vrf_name="PROD", rd="65001:100", vni=100100):
        vni_peer = MagicMock()
        vni_peer.vni = _attr(vni)

        rt_import = MagicMock()
        rt_import.target = _attr("65001:100")
        rt_export = MagicMock()
        rt_export.target = _attr("65001:100")

        vrf_node = MagicMock()
        vrf_node.name = _attr(vrf_name)
        vrf_node.route_distinguisher = _attr(rd)
        vrf_node.vrf_id = _attr(None)
        vrf_node.l3vni = _rel_one(vni_peer)
        vrf_node.import_targets = _rel_many([rt_import])
        vrf_node.export_targets = _rel_many([rt_export])

        assignment = MagicMock()
        assignment.vrf = _rel_one(vrf_node)

        return assignment

    async def test_returns_vrf_intents(self, client):
        assignment = self._make_assignment()
        client._sdk.filters = AsyncMock(return_value=[assignment])

        results = await client.get_device_vrfs("leaf1")

        assert len(results) == 1
        assert isinstance(results[0], VrfIntent)
        assert results[0].name == "PROD"
        assert results[0].route_distinguisher == "65001:100"
        assert results[0].l3vni == 100100
        assert "65001:100" in results[0].import_targets

    async def test_empty_when_no_assignments(self, client):
        client._sdk.filters = AsyncMock(return_value=[])

        results = await client.get_device_vrfs("leaf1")

        assert results == []

    async def test_caching(self, client):
        assignment = self._make_assignment()
        client._sdk.filters = AsyncMock(return_value=[assignment])

        await client.get_device_vrfs("leaf1")
        await client.get_device_vrfs("leaf1")

        assert client._sdk.filters.call_count == 1


# ---------------------------------------------------------------------------
# get_device_vtep
# ---------------------------------------------------------------------------


class TestGetDeviceVtep:
    def _make_vtep(self, src_addr="10.255.0.1", udp_port=4789):
        vlan_node = MagicMock()
        vlan_node.vlan_id = _attr(100)
        vni_node = MagicMock()
        vni_node.vni = _attr(10100)

        mapping = MagicMock()
        mapping.vlan = _rel_one(vlan_node)
        mapping.vni = _rel_one(vni_node)

        vtep = MagicMock()
        vtep.source_address = _attr(src_addr)
        vtep.udp_port = _attr(udp_port)
        vtep.learn_restrict = _attr(True)
        vtep.vlan_vni_mappings = _rel_many([mapping])

        return vtep

    async def test_returns_vtep_intent(self, client):
        vtep = self._make_vtep()
        client._sdk.filters = AsyncMock(return_value=[vtep])

        result = await client.get_device_vtep("leaf1")

        assert isinstance(result, VtepIntent)
        assert result.source_address == "10.255.0.1"
        assert result.udp_port == 4789
        assert result.learn_restrict is True
        assert (100, 10100) in result.vlan_vni_mappings

    async def test_returns_none_when_no_vtep(self, client):
        client._sdk.filters = AsyncMock(return_value=[])

        result = await client.get_device_vtep("leaf1")

        assert result is None


# ---------------------------------------------------------------------------
# get_device_evpn_instances
# ---------------------------------------------------------------------------


class TestGetDeviceEvpnInstances:
    def _make_evpn_instance(self, rd="65001:100", rt_import="65001:100", rt_export="65001:100"):
        vlan_node = MagicMock()
        vlan_node.vlan_id = _attr(100)

        node = MagicMock()
        node.route_distinguisher = _attr(rd)
        node.route_target_import = _attr(rt_import)
        node.route_target_export = _attr(rt_export)
        node.redistribute_learned = _attr(True)
        node.vlan = _rel_one(vlan_node)

        return node

    async def test_returns_evpn_instance_intents(self, client):
        evpn_node = self._make_evpn_instance()
        client._sdk.filters = AsyncMock(return_value=[evpn_node])

        results = await client.get_device_evpn_instances("leaf1")

        assert len(results) == 1
        assert isinstance(results[0], EvpnInstanceIntent)
        assert results[0].route_distinguisher == "65001:100"
        assert results[0].redistribute_learned is True
        assert results[0].vlan_id == 100

    async def test_empty_when_no_instances(self, client):
        client._sdk.filters = AsyncMock(return_value=[])

        results = await client.get_device_evpn_instances("leaf1")

        assert results == []


# ---------------------------------------------------------------------------
# get_mlag_domain
# ---------------------------------------------------------------------------


class TestGetMlagDomain:
    def _make_domain(self, device_names=("leaf1", "leaf2")):
        devices = []
        for dname in device_names:
            d = MagicMock()
            d.name = _attr(dname)
            devices.append(d)

        peer_vlan_node = MagicMock()
        peer_vlan_node.vlan_id = _attr(4094)

        domain = MagicMock()
        domain.domain_id = _attr("1")
        domain.virtual_mac = _attr("00:1c:73:00:00:01")
        domain.heartbeat_vrf = _attr("MGMT")
        domain.dual_primary_detection = _attr(True)
        domain.dual_primary_delay = _attr(10)
        domain.dual_primary_action = _attr("errDisable")
        domain.devices = _rel_many(devices)
        domain.peer_vlan = _rel_one(peer_vlan_node)

        return domain

    async def test_returns_mlag_domain_intent(self, client):
        domain = self._make_domain()
        client._sdk.all = AsyncMock(return_value=[domain])

        result = await client.get_mlag_domain("leaf1")

        assert isinstance(result, MlagDomainIntent)
        assert result.domain_id == "1"
        assert result.virtual_mac == "00:1c:73:00:00:01"
        assert "leaf1" in result.peer_devices
        assert "leaf2" in result.peer_devices

    async def test_returns_none_when_device_not_in_any_domain(self, client):
        domain = self._make_domain(device_names=("leaf3", "leaf4"))
        client._sdk.all = AsyncMock(return_value=[domain])

        result = await client.get_mlag_domain("leaf1")

        assert result is None

    async def test_caching(self, client):
        domain = self._make_domain()
        client._sdk.all = AsyncMock(return_value=[domain])

        await client.get_mlag_domain("leaf1")
        await client.get_mlag_domain("leaf1")

        assert client._sdk.all.call_count == 1


# ---------------------------------------------------------------------------
# get_mlag_peer_config
# ---------------------------------------------------------------------------


class TestGetMlagPeerConfig:
    def _make_peer_config(self):
        peer_link_node = MagicMock()
        peer_link_node.name = _attr("Port-Channel1")

        cfg = MagicMock()
        cfg.local_interface_ip = _attr("192.168.255.0/31")
        cfg.peer_address = _attr("192.168.255.1")
        cfg.heartbeat_peer_ip = _attr("192.168.1.2")
        cfg.peer_link = _rel_one(peer_link_node)

        return cfg

    async def test_returns_mlag_peer_config_intent(self, client):
        cfg = self._make_peer_config()
        client._sdk.filters = AsyncMock(return_value=[cfg])

        result = await client.get_mlag_peer_config("leaf1")

        assert isinstance(result, MlagPeerConfigIntent)
        assert result.local_interface_ip == "192.168.255.0/31"
        assert result.peer_address == "192.168.255.1"
        assert result.peer_link == "Port-Channel1"

    async def test_returns_none_when_no_config(self, client):
        client._sdk.filters = AsyncMock(return_value=[])

        result = await client.get_mlag_peer_config("leaf1")

        assert result is None


# ---------------------------------------------------------------------------
# Async context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    async def test_context_manager(self):
        with patch("infrahub_client.client.InfrahubClient"):
            async with FabricInfrahubClient(
                url="http://infrahub:8080", api_token="token"
            ) as client:
                assert isinstance(client, FabricInfrahubClient)


# ---------------------------------------------------------------------------
# Cache TTL expiry
# ---------------------------------------------------------------------------


class TestCacheTtl:
    async def test_expired_cache_triggers_new_sdk_call(self, client):
        device_node = _make_device()
        client._sdk.get = AsyncMock(return_value=device_node)

        await client.get_device("leaf1")
        # Manually expire the cache entry
        client._cache["device:leaf1"] = (client._cache["device:leaf1"][0], 0.0)
        await client.get_device("leaf1")

        assert client._sdk.get.call_count == 2


# ---------------------------------------------------------------------------
# InfrahubQueryError propagation
# ---------------------------------------------------------------------------


class TestQueryError:
    async def test_sdk_unexpected_error_raises_query_error(self, client):
        client._sdk.get = AsyncMock(side_effect=Exception("connection refused"))

        with pytest.raises(InfrahubQueryError):
            await client.get_device_bgp_config("leaf1")
