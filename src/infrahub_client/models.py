"""Pydantic v2 models for typed Infrahub fabric intent responses."""

from pydantic import BaseModel, ConfigDict


class DeviceIntent(BaseModel):
    """Intent model for an Infrahub InfraDevice node."""

    model_config = ConfigDict(frozen=True)

    name: str
    role: str
    status: str
    platform: str | None = None
    site: str | None = None
    asn: int | None = None


class VlanIntent(BaseModel):
    """Intent model for an Infrahub InfraVLAN node."""

    model_config = ConfigDict(frozen=True)

    vlan_id: int
    name: str
    status: str
    vlan_type: str
    vni: int | None = None
    stp_enabled: bool


class VniIntent(BaseModel):
    """Intent model for an Infrahub InfraVNI node."""

    model_config = ConfigDict(frozen=True)

    vni: int
    vni_type: str
    description: str | None = None


class BgpRouterConfigIntent(BaseModel):
    """Intent model for an Infrahub InfraBGPRouterConfig node."""

    model_config = ConfigDict(frozen=True)

    router_id: str
    local_asn: int
    default_ipv4_unicast: bool
    ecmp_max_paths: int


class BgpPeerGroupIntent(BaseModel):
    """Intent model for an Infrahub InfraBGPPeerGroup node."""

    model_config = ConfigDict(frozen=True)

    name: str
    peer_group_type: str
    remote_asn: int | None = None
    update_source: str | None = None
    send_community: bool
    ebgp_multihop: int | None = None
    next_hop_unchanged: bool


class BgpSessionIntent(BaseModel):
    """Intent model for an Infrahub InfraBGPSession node."""

    model_config = ConfigDict(frozen=True)

    peer_address: str
    description: str | None = None
    enabled: bool
    peer_group: str | None = None
    remote_asn: int | None = None


class VrfIntent(BaseModel):
    """Intent model for an Infrahub InfraVRF node."""

    model_config = ConfigDict(frozen=True)

    name: str
    route_distinguisher: str | None = None
    vrf_id: int | None = None
    l3vni: int | None = None
    import_targets: list[str]
    export_targets: list[str]


class VtepIntent(BaseModel):
    """Intent model for an Infrahub InfraVTEP node."""

    model_config = ConfigDict(frozen=True)

    source_address: str
    udp_port: int
    learn_restrict: bool
    vlan_vni_mappings: list[tuple[int, int]]


class MlagDomainIntent(BaseModel):
    """Intent model for an Infrahub InfraMlagDomain node."""

    model_config = ConfigDict(frozen=True)

    domain_id: str
    virtual_mac: str
    heartbeat_vrf: str
    dual_primary_detection: bool
    dual_primary_delay: int
    dual_primary_action: str
    peer_devices: list[str]


class MlagPeerConfigIntent(BaseModel):
    """Intent model for an Infrahub InfraMlagPeerConfig node."""

    model_config = ConfigDict(frozen=True)

    local_interface_ip: str
    peer_address: str
    heartbeat_peer_ip: str
    peer_link: str


class EvpnInstanceIntent(BaseModel):
    """Intent model for an Infrahub InfraEVPNInstance node."""

    model_config = ConfigDict(frozen=True)

    route_distinguisher: str
    route_target_import: str
    route_target_export: str
    redistribute_learned: bool
    vlan_id: int
