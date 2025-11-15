#!/usr/bin/env python3
"""
AWS Service Discovery (Cloud Map) Export Script

Exports AWS Cloud Map service discovery resources:
- Namespaces (public DNS, private DNS, HTTP)
- Services and service instances
- Service registries and health check configurations
- Custom attributes and instance metadata
- DNS configurations and routing policies

Features:
- Complete namespace and service inventory
- Instance registration tracking
- Health status monitoring
- DNS configuration details
- Multi-region support
- Comprehensive multi-worksheet export

Note: Requires servicediscovery:List* and servicediscovery:Get* permissions
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Standard utils import pattern
try:
    import utils
except ImportError:
    script_dir = Path(__file__).parent.absolute()
    if script_dir.name.lower() == 'scripts':
        sys.path.append(str(script_dir.parent))
    else:
        sys.path.append(str(script_dir))
    import utils

# Check required packages
utils.check_required_packages(['boto3', 'pandas', 'openpyxl'])

# Setup logging
logger = utils.setup_logging('servicediscovery-export')
utils.log_script_start('servicediscovery-export', 'Export AWS Service Discovery (Cloud Map) resources')


@utils.aws_error_handler("Collecting namespaces", default_return=[])
def collect_namespaces(region: str) -> List[Dict[str, Any]]:
    """Collect all Service Discovery namespaces in a region."""
    sd = utils.get_boto3_client('servicediscovery', region_name=region)
    namespaces = []

    paginator = sd.get_paginator('list_namespaces')
    for page in paginator.paginate():
        for ns in page.get('Namespaces', []):
            namespace_id = ns.get('Id')

            # Get detailed namespace information
            try:
                detail = sd.get_namespace(Id=namespace_id)
                ns_detail = detail.get('Namespace', {})

                # Extract properties
                props = ns_detail.get('Properties', {})
                dns_props = props.get('DnsProperties', {})
                http_props = props.get('HttpProperties', {})

                namespaces.append({
                    'Region': region,
                    'NamespaceId': namespace_id,
                    'NamespaceArn': ns.get('Arn', 'N/A'),
                    'Name': ns.get('Name', 'N/A'),
                    'Type': ns.get('Type', 'N/A'),
                    'Description': ns.get('Description', 'N/A'),
                    'ServiceCount': ns.get('ServiceCount', 0),
                    'CreateDate': ns.get('CreateDate'),
                    'CreatorRequestId': ns_detail.get('CreatorRequestId', 'N/A'),
                    'HostedZoneId': dns_props.get('HostedZoneId', 'N/A'),
                    'SOA': str(dns_props.get('SOA', {})) if dns_props.get('SOA') else 'N/A',
                    'HttpName': http_props.get('HttpName', 'N/A'),
                })
            except Exception:
                # Fallback to summary data if detailed fetch fails
                namespaces.append({
                    'Region': region,
                    'NamespaceId': namespace_id,
                    'NamespaceArn': ns.get('Arn', 'N/A'),
                    'Name': ns.get('Name', 'N/A'),
                    'Type': ns.get('Type', 'N/A'),
                    'Description': ns.get('Description', 'N/A'),
                    'ServiceCount': ns.get('ServiceCount', 0),
                    'CreateDate': ns.get('CreateDate'),
                    'CreatorRequestId': 'N/A',
                    'HostedZoneId': 'N/A',
                    'SOA': 'N/A',
                    'HttpName': 'N/A',
                })

    return namespaces


@utils.aws_error_handler("Collecting services", default_return=[])
def collect_services(region: str) -> List[Dict[str, Any]]:
    """Collect all Service Discovery services across namespaces."""
    sd = utils.get_boto3_client('servicediscovery', region_name=region)
    services = []

    paginator = sd.get_paginator('list_services')
    for page in paginator.paginate():
        for svc in page.get('Services', []):
            service_id = svc.get('Id')

            # Get detailed service information
            try:
                detail = sd.get_service(Id=service_id)
                svc_detail = detail.get('Service', {})

                # Extract health check config
                health_config = svc_detail.get('HealthCheckConfig', {})
                health_custom_config = svc_detail.get('HealthCheckCustomConfig', {})

                # Extract DNS config
                dns_config = svc_detail.get('DnsConfig', {})
                dns_records = []
                for record in dns_config.get('DnsRecords', []):
                    dns_records.append(f"{record.get('Type')}:{record.get('TTL')}")

                services.append({
                    'Region': region,
                    'ServiceId': service_id,
                    'ServiceArn': svc.get('Arn', 'N/A'),
                    'Name': svc.get('Name', 'N/A'),
                    'NamespaceId': dns_config.get('NamespaceId', 'N/A'),
                    'Description': svc.get('Description', 'N/A'),
                    'InstanceCount': svc.get('InstanceCount', 0),
                    'CreateDate': svc.get('CreateDate'),
                    'CreatorRequestId': svc_detail.get('CreatorRequestId', 'N/A'),
                    'Type': svc_detail.get('Type', 'N/A'),
                    'DnsRecords': ', '.join(dns_records) if dns_records else 'N/A',
                    'RoutingPolicy': dns_config.get('RoutingPolicy', 'N/A'),
                    'HealthCheckType': health_config.get('Type', health_custom_config.get('FailureThreshold', 'N/A')),
                    'HealthCheckPath': health_config.get('ResourcePath', 'N/A'),
                    'HealthCheckFailureThreshold': health_custom_config.get('FailureThreshold', 'N/A'),
                })
            except Exception:
                # Fallback to summary data
                services.append({
                    'Region': region,
                    'ServiceId': service_id,
                    'ServiceArn': svc.get('Arn', 'N/A'),
                    'Name': svc.get('Name', 'N/A'),
                    'NamespaceId': 'N/A',
                    'Description': svc.get('Description', 'N/A'),
                    'InstanceCount': svc.get('InstanceCount', 0),
                    'CreateDate': svc.get('CreateDate'),
                    'CreatorRequestId': 'N/A',
                    'Type': 'N/A',
                    'DnsRecords': 'N/A',
                    'RoutingPolicy': 'N/A',
                    'HealthCheckType': 'N/A',
                    'HealthCheckPath': 'N/A',
                    'HealthCheckFailureThreshold': 'N/A',
                })

    return services


@utils.aws_error_handler("Collecting service instances", default_return=[])
def collect_instances(region: str, service_id: str) -> List[Dict[str, Any]]:
    """Collect instances registered to a specific service."""
    sd = utils.get_boto3_client('servicediscovery', region_name=region)
    instances = []

    try:
        paginator = sd.get_paginator('list_instances')
        for page in paginator.paginate(ServiceId=service_id):
            for inst in page.get('Instances', []):
                # Extract attributes
                attributes = inst.get('Attributes', {})

                instances.append({
                    'Region': region,
                    'ServiceId': service_id,
                    'InstanceId': inst.get('Id', 'N/A'),
                    'IPv4': attributes.get('AWS_INSTANCE_IPV4', 'N/A'),
                    'IPv6': attributes.get('AWS_INSTANCE_IPV6', 'N/A'),
                    'Port': attributes.get('AWS_INSTANCE_PORT', 'N/A'),
                    'EC2InstanceId': attributes.get('AWS_EC2_INSTANCE_ID', 'N/A'),
                    'AZ': attributes.get('AWS_AVAILABILITY_ZONE', 'N/A'),
                    'Region_Attr': attributes.get('AWS_REGION', 'N/A'),
                    'CustomAttributes': str({k: v for k, v in attributes.items() if not k.startswith('AWS_')}) if attributes else 'N/A',
                })
    except Exception:
        pass

    return instances


def main():
    """Main execution function."""
    try:
        # Get account information
        account_id, account_name = utils.get_account_info()
        utils.log_info(f"Exporting Service Discovery (Cloud Map) resources for account: {account_name} ({account_id})")

        # Prompt for regions
        utils.log_info("Service Discovery is a regional service.")
        regions = utils.prompt_region_selection(
            service_name="Service Discovery",
            default_to_all=False
        )

        if not regions:
            utils.log_error("No regions selected. Exiting.")
            return

        utils.log_info(f"Scanning {len(regions)} region(s) for Service Discovery resources...")

        # Collect all resources
        all_namespaces = []
        all_services = []
        all_instances = []

        for idx, region in enumerate(regions, 1):
            utils.log_info(f"[{idx}/{len(regions)}] Processing region: {region}")

            # Collect namespaces
            namespaces = collect_namespaces(region)
            if namespaces:
                utils.log_info(f"  Found {len(namespaces)} namespace(s)")
                all_namespaces.extend(namespaces)

            # Collect services
            services = collect_services(region)
            if services:
                utils.log_info(f"  Found {len(services)} service(s)")
                all_services.extend(services)

                # Collect instances for each service (limit to first 20 services)
                for service in services[:20]:
                    service_id = service['ServiceId']
                    instances = collect_instances(region, service_id)
                    all_instances.extend(instances)

        if not all_namespaces and not all_services:
            utils.log_warning("No Service Discovery resources found in any selected region.")
            utils.log_info("Creating empty export file...")

        utils.log_info(f"Total namespaces found: {len(all_namespaces)}")
        utils.log_info(f"Total services found: {len(all_services)}")
        utils.log_info(f"Total instances found: {len(all_instances)}")

        # Create DataFrames
        df_namespaces = utils.prepare_dataframe_for_export(pd.DataFrame(all_namespaces))
        df_services = utils.prepare_dataframe_for_export(pd.DataFrame(all_services))
        df_instances = utils.prepare_dataframe_for_export(pd.DataFrame(all_instances))

        # Create summary
        summary_data = []
        summary_data.append({'Metric': 'Total Namespaces', 'Value': len(all_namespaces)})
        summary_data.append({'Metric': 'Total Services', 'Value': len(all_services)})
        summary_data.append({'Metric': 'Total Instances', 'Value': len(all_instances)})
        summary_data.append({'Metric': 'Regions Scanned', 'Value': len(regions)})

        if not df_namespaces.empty:
            dns_namespaces = len(df_namespaces[df_namespaces['Type'].str.contains('DNS', na=False)])
            http_namespaces = len(df_namespaces[df_namespaces['Type'] == 'HTTP'])

            summary_data.append({'Metric': 'DNS Namespaces', 'Value': dns_namespaces})
            summary_data.append({'Metric': 'HTTP Namespaces', 'Value': http_namespaces})

        df_summary = utils.prepare_dataframe_for_export(pd.DataFrame(summary_data))

        # Create filtered views
        df_dns_namespaces = pd.DataFrame()
        df_http_namespaces = pd.DataFrame()

        if not df_namespaces.empty:
            df_dns_namespaces = df_namespaces[df_namespaces['Type'].str.contains('DNS', na=False)]
            df_http_namespaces = df_namespaces[df_namespaces['Type'] == 'HTTP']

        # Export to Excel
        filename = utils.create_export_filename(account_name, 'servicediscovery', 'all')

        sheets = {
            'Summary': df_summary,
            'Namespaces': df_namespaces,
            'DNS Namespaces': df_dns_namespaces,
            'HTTP Namespaces': df_http_namespaces,
            'Services': df_services,
            'Service Instances': df_instances,
        }

        utils.save_multiple_dataframes_to_excel(sheets, filename)

        # Log summary
        utils.log_export_summary(
            total_items=len(all_namespaces) + len(all_services) + len(all_instances),
            item_type='Service Discovery Resources',
            filename=filename
        )

        utils.log_info(f"  Namespaces: {len(all_namespaces)}")
        utils.log_info(f"  Services: {len(all_services)}")
        utils.log_info(f"  Instances: {len(all_instances)}")

        utils.log_success("Service Discovery export completed successfully!")

    except Exception as e:
        utils.log_error(f"Failed to export Service Discovery resources: {str(e)}")
        raise


if __name__ == "__main__":
    main()
