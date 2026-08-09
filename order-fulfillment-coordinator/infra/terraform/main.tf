terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

variable "tenancy_ocid" {
  description = "OCI Tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI User OCID"
  type        = string
}

variable "fingerprint" {
  description = "OCI API Key Fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to OCI API private key"
  type        = string
}

variable "region" {
  description = "OCI Region"
  type        = string
  default     = "us-ashburn-1"
}

variable "compartment_ocid" {
  description = "OCI Compartment OCID"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key content"
  type        = string
}

variable "domain_name" {
  description = "Domain name for Caddy SSL"
  type        = string
  default     = ""
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

resource "oci_core_vcn" "wherehouse_vcn" {
  compartment_id = var.compartment_ocid
  display_name   = "fulfillos-vcn"
  cidr_blocks    = ["10.0.0.0/16"]
  dns_label      = "fulfillos"
}

resource "oci_core_internet_gateway" "wherehouse_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.wherehouse_vcn.id
  display_name   = "fulfillos-igw"
}

resource "oci_core_route_table" "wherehouse_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.wherehouse_vcn.id
  display_name   = "fulfillos-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.wherehouse_igw.id
  }
}

resource "oci_core_security_list" "wherehouse_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.wherehouse_vcn.id
  display_name   = "fulfillos-sl"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      max = 22
      min = 22
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      max = 80
      min = 80
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      max = 443
      min = 443
    }
  }
}

resource "oci_core_subnet" "wherehouse_subnet" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.wherehouse_vcn.id
  display_name   = "fulfillos-subnet"
  cidr_block     = "10.0.1.0/24"
  dns_label      = "fulfillos"
  route_table_id = oci_core_route_table.wherehouse_rt.id

  security_list_ids = [oci_core_security_list.wherehouse_sl.id]
}

resource "oci_core_instance" "wherehouse_vm" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "fulfillos"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 4
    memory_in_gbs = 24
  }

  source_details {
    source_id   = "canonical:ap-sydney-1:canonicalubuntu2204:2025.04.15-0"
    source_type = "image"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      domain_name = var.domain_name
      repo_url    = "https://github.com/muhammadharis-web/wherehouse-os-.git"
    }))
  }

  preserve_boot_volume = false
}

resource "oci_core_public_ip" "wherehouse_ip" {
  compartment_id = var.compartment_ocid
  display_name   = "fulfillos-public-ip"
  lifetime       = "RESERVED"
  private_ip_id  = oci_core_instance.wherehouse_vm.private_ip
}

output "instance_ip" {
  value = oci_core_public_ip.wherehouse_ip.ip_address
}

output "instance_ocid" {
  value = oci_core_instance.wherehouse_vm.id
}
