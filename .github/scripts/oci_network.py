"""Inspect the existing instance; optionally attach a dedicated TCP 443 NSG.

No VM, subnet, route, existing security-list rule, or application service is
replaced. Credentials stay in runner memory. Inspect mode makes no changes.
"""
from __future__ import annotations

import hashlib
import json
import os

from cryptography.hazmat.primitives import serialization
import oci

REGION = "ap-hyderabad-1"
INSTANCE = "ocid1.instance.oc1.ap-hyderabad-1.anuhsljrjp76cqicl66s4ny43h3ozu6sh7tueov6kb6de7yclv435dkp5liq"
COMPARTMENT = "ocid1.tenancy.oc1..aaaaaaaaa4acqe2kwhnom3kj7vgf4dy5cw5ymouzkrs47nw54hmwthjfxaoq"
PUBLIC_IP = "140.245.218.97"
GROUP_NAME = "warehouse-os-public-https"


def permits_https(rule) -> bool:
    if getattr(rule, "direction", "INGRESS") != "INGRESS":
        return False
    if rule.source != "0.0.0.0/0" or rule.protocol not in ("6", "all"):
        return False
    tcp = rule.tcp_options
    ports = tcp.destination_port_range if tcp else None
    return rule.protocol == "all" or ports is None or ports.min <= 443 <= ports.max


def main() -> None:
    mode = os.environ.get("NETWORK_MODE", "inspect")
    if mode not in ("inspect", "allow_https"):
        raise RuntimeError("Unsupported network operation")
    required = ("OCI_TENANCY", "OCI_USER", "OCI_FINGERPRINT", "OCI_KEY")
    if any(not os.environ.get(name) for name in required):
        raise RuntimeError("Required existing OCI API secret is missing")
    if os.environ["OCI_TENANCY"].strip() != COMPARTMENT:
        raise RuntimeError("Credential tenancy differs from the verified existing instance")
    key_content = os.environ["OCI_KEY"]
    key = serialization.load_pem_private_key(key_content.encode(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    digest = hashlib.md5(public, usedforsecurity=False).hexdigest()
    fingerprint = ":".join(digest[i:i+2] for i in range(0, len(digest), 2))
    if fingerprint.lower() != os.environ["OCI_FINGERPRINT"].strip().lower():
        raise RuntimeError("OCI API signing key does not match its configured fingerprint")
    config = {"region": REGION, "tenancy": COMPARTMENT, "user": os.environ["OCI_USER"].strip(), "fingerprint": fingerprint, "key_content": key_content}
    signer = oci.signer.Signer(config["tenancy"], config["user"], fingerprint, None, private_key_content=key_content)
    compute = oci.core.ComputeClient(config, signer=signer, timeout=(10, 30))
    network = oci.core.VirtualNetworkClient(config, signer=signer, timeout=(10, 30))
    instance = compute.get_instance(INSTANCE).data
    if instance.compartment_id != COMPARTMENT or instance.lifecycle_state != "RUNNING":
        raise RuntimeError("Verified instance identity/state differs; refusing changes")
    attachments = oci.pagination.list_call_get_all_results(compute.list_vnic_attachments, COMPARTMENT, instance_id=INSTANCE).data
    matches = []
    for attachment in attachments:
        if attachment.lifecycle_state == "ATTACHED":
            response = network.get_vnic(attachment.vnic_id)
            if response.data.public_ip == PUBLIC_IP:
                matches.append(response)
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one VNIC with the verified public IP")
    vnic_response = matches[0]
    vnic = vnic_response.data
    subnet = network.get_subnet(vnic.subnet_id).data
    rules = []
    for list_id in subnet.security_list_ids:
        rules.extend(network.get_security_list(list_id).data.ingress_security_rules)
    for group_id in vnic.nsg_ids or []:
        rules.extend(oci.pagination.list_call_get_all_results(network.list_network_security_group_security_rules, group_id, direction="INGRESS").data)
    already_allowed = any(permits_https(rule) for rule in rules)
    result = {"region": REGION, "public_ip": PUBLIC_IP, "mode": mode, "public_tcp_443_allowed": already_allowed, "changed": False}
    if mode == "allow_https" and not already_allowed:
        groups = oci.pagination.list_call_get_all_results(network.list_network_security_groups, compartment_id=COMPARTMENT, vcn_id=subnet.vcn_id, display_name=GROUP_NAME).data
        groups = [group for group in groups if group.lifecycle_state == "AVAILABLE" and (group.freeform_tags or {}).get("warehouse_instance") == INSTANCE]
        if len(groups) > 1:
            raise RuntimeError("Ambiguous dedicated HTTPS security group")
        group = groups[0] if groups else network.create_network_security_group(oci.core.models.CreateNetworkSecurityGroupDetails(
            compartment_id=COMPARTMENT, vcn_id=subnet.vcn_id, display_name=GROUP_NAME,
            freeform_tags={"warehouse_instance": INSTANCE},
        )).data
        existing = oci.pagination.list_call_get_all_results(network.list_network_security_group_security_rules, group.id, direction="INGRESS").data
        if not any(permits_https(rule) for rule in existing):
            network.add_network_security_group_security_rules(group.id, oci.core.models.AddNetworkSecurityGroupSecurityRulesDetails(security_rules=[
                oci.core.models.AddSecurityRuleDetails(direction="INGRESS", protocol="6", source="0.0.0.0/0", source_type="CIDR_BLOCK", is_stateless=False,
                    description="Warehouse OS public HTTPS on verified existing VNIC",
                    tcp_options=oci.core.models.TcpOptions(destination_port_range=oci.core.models.PortRange(min=443, max=443))),
            ]))
        # Optimistic concurrency preserves all pre-existing VNIC group membership.
        current = network.get_vnic(vnic.id)
        ids = list(current.data.nsg_ids or [])
        if group.id not in ids:
            network.update_vnic(vnic.id, oci.core.models.UpdateVnicDetails(nsg_ids=ids+[group.id]), if_match=current.headers["etag"])
        result.update(changed=True, public_tcp_443_allowed=True, dedicated_nsg_id=group.id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except oci.exceptions.ServiceError as exc:
        print(json.dumps({"network_operation_failed": True, "http_status": exc.status, "oci_error_code": exc.code}))
        raise SystemExit(1)
    except Exception as exc:
        # Avoid raw SDK/config tracebacks containing credential material.
        print(json.dumps({"network_operation_failed": True, "error_type": type(exc).__name__, "reason": str(exc) if isinstance(exc, RuntimeError) else "Invalid credential or SDK configuration; values withheld"}))
        raise SystemExit(1)
