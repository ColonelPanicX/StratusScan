#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Route 53 Export Tool
Version: v1.0.0
Date: OCT-27-2025

Description:
This script exports comprehensive Route 53 information from AWS including hosted zones,
DNS records, resolver endpoints, resolver rules, DNS Firewall configurations, and query
logging settings into an Excel file with separate worksheets. The output filename
includes the AWS account name based on the account ID mapping in the configuration.

Route 53 is a global service, but some features (like Resolver) are regional.
"""

import os
import sys
import json
import datetime
import time
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path

# Add path to import utils module
try:
    import utils
except ImportError:
    script_dir = Path(__file__).parent.absolute()
    if script_dir.name.lower() == 'scripts':
        sys.path.append(str(script_dir.parent))
    else:
        sys.path.append(str(script_dir))

    try:
        import utils
    except ImportError:
        print("ERROR: Could not import the utils module. Make sure utils.py is in the StratusScan directory.")
        sys.exit(1)

def print_title():
    """Print the title and header of the script to the console."""
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                    ")
    print("====================================================================")
    print("               AWS ROUTE 53 EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.0.0                        Date: OCT-27-2025")
    print("Environment: AWS Commercial")
    print("====================================================================")

    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_name = utils.get_account_name(account_id, default=account_id)

        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except NoCredentialsError:
        print("\nERROR: No AWS credentials found.")
        print("Please configure your AWS credentials using one of the following methods:")
        print("  1. AWS CLI: aws configure")
        print("  2. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("  3. IAM role (if running on EC2)")
        sys.exit(1)
    except Exception as e:
        print("Could not determine account information.")
        account_id = "unknown"
        account_name = "unknown"

    print("====================================================================")
    return account_id, account_name

def check_and_install_dependencies():
    """Check and install required dependencies if needed."""
    required_packages = ['pandas', 'openpyxl', 'boto3']

    for package in required_packages:
        try:
            __import__(package)
            utils.log_info(f"[OK] {package} is already installed")
        except ImportError:
            response = input(f"{package} is not installed. Do you want to install it? (y/n): ")
            if response.lower() == 'y':
                try:
                    import subprocess
                    print(f"Installing {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    utils.log_success(f"Successfully installed {package}")
                except Exception as e:
                    utils.log_error(f"Error installing {package}", e)
                    sys.exit(1)
            else:
                print(f"Cannot proceed without {package}. Exiting...")
                sys.exit(1)

def collect_hosted_zones_data():
    """
    Collect all Route 53 hosted zones information.
    Route 53 is a global service.

    Returns:
        list: List of dictionaries with hosted zone information
    """
    print("\n=== COLLECTING HOSTED ZONES INFORMATION ===")
    all_zones = []

    try:
        # Route 53 is global, no region needed
        route53_client = boto3.client('route53')

        # Get all hosted zones using paginator
        paginator = route53_client.get_paginator('list_hosted_zones')
        page_iterator = paginator.paginate()

        for page in page_iterator:
            zones = page.get('HostedZones', [])

            for zone in zones:
                try:
                    zone_id = zone['Id'].split('/')[-1]  # Remove '/hostedzone/' prefix
                    zone_name = zone['Name']
                    print(f"  Processing hosted zone: {zone_name} ({zone_id})")

                    # Get zone details including resource record set count
                    zone_details = route53_client.get_hosted_zone(Id=zone['Id'])
                    hosted_zone = zone_details['HostedZone']

                    # Get VPC associations for private zones
                    vpc_associations = []
                    if hosted_zone.get('Config', {}).get('PrivateZone', False):
                        vpcs = zone_details.get('VPCs', [])
                        for vpc in vpcs:
                            vpc_associations.append(f"{vpc.get('VPCId', 'N/A')} ({vpc.get('VPCRegion', 'N/A')})")

                    vpc_assoc_str = ', '.join(vpc_associations) if vpc_associations else 'N/A'

                    # Get tags
                    tags = {}
                    try:
                        tags_response = route53_client.list_tags_for_resource(
                            ResourceType='hostedzone',
                            ResourceId=zone_id
                        )
                        for tag in tags_response.get('Tags', []):
                            tags[tag['Key']] = tag['Value']
                    except Exception as e:
                        utils.log_warning(f"Could not retrieve tags for zone {zone_id}: {e}")

                    # Compile zone data
                    zone_data = {
                        'Hosted Zone ID': zone_id,
                        'Name': zone_name,
                        'Type': 'Private' if hosted_zone.get('Config', {}).get('PrivateZone', False) else 'Public',
                        'Resource Record Set Count': hosted_zone.get('ResourceRecordSetCount', 0),
                        'Caller Reference': zone.get('CallerReference', 'N/A'),
                        'VPC Associations': vpc_assoc_str,
                        'Comment': hosted_zone.get('Config', {}).get('Comment', 'N/A'),
                        'Tags': json.dumps(tags) if tags else 'N/A'
                    }

                    all_zones.append(zone_data)
                    time.sleep(0.1)  # Rate limiting

                except Exception as e:
                    utils.log_error(f"Error processing hosted zone {zone.get('Name', 'unknown')}", e)
                    continue

        utils.log_success(f"Total hosted zones collected: {len(all_zones)}")

    except Exception as e:
        utils.log_error("Error collecting hosted zones", e)

    return all_zones

def collect_record_sets_data():
    """
    Collect all DNS record sets from all hosted zones.

    Returns:
        list: List of dictionaries with DNS record information
    """
    print("\n=== COLLECTING DNS RECORD SETS INFORMATION ===")
    all_records = []

    try:
        route53_client = boto3.client('route53')

        # Get all hosted zones first
        paginator = route53_client.get_paginator('list_hosted_zones')
        page_iterator = paginator.paginate()

        for page in page_iterator:
            zones = page.get('HostedZones', [])

            for zone in zones:
                zone_id = zone['Id']
                zone_name = zone['Name']
                print(f"  Collecting records for zone: {zone_name}")

                try:
                    # Get all record sets for this zone
                    record_paginator = route53_client.get_paginator('list_resource_record_sets')
                    record_iterator = record_paginator.paginate(HostedZoneId=zone_id)

                    for record_page in record_iterator:
                        record_sets = record_page.get('ResourceRecordSets', [])

                        for record in record_sets:
                            try:
                                record_name = record.get('Name', 'N/A')
                                record_type = record.get('Type', 'N/A')

                                # Handle alias records
                                if record.get('AliasTarget'):
                                    alias_target = record['AliasTarget']
                                    record_value = f"ALIAS -> {alias_target.get('DNSName', 'N/A')}"
                                    alias_zone_id = alias_target.get('HostedZoneId', 'N/A')
                                    evaluate_health = alias_target.get('EvaluateTargetHealth', False)
                                    ttl = 'N/A (Alias)'
                                else:
                                    # Handle regular records
                                    resource_records = record.get('ResourceRecords', [])
                                    values = [rr.get('Value', '') for rr in resource_records]
                                    record_value = ', '.join(values) if values else 'N/A'
                                    # Truncate very long values (like TXT records)
                                    if len(record_value) > 500:
                                        record_value = record_value[:500] + '... (truncated)'
                                    alias_zone_id = 'N/A'
                                    evaluate_health = 'N/A'
                                    ttl = record.get('TTL', 'N/A')

                                # Routing policy information
                                routing_policy = 'Simple'
                                routing_details = ''

                                if record.get('Weight') is not None:
                                    routing_policy = 'Weighted'
                                    routing_details = f"Weight: {record['Weight']}, SetID: {record.get('SetIdentifier', 'N/A')}"
                                elif record.get('Region'):
                                    routing_policy = 'Latency'
                                    routing_details = f"Region: {record['Region']}, SetID: {record.get('SetIdentifier', 'N/A')}"
                                elif record.get('Failover'):
                                    routing_policy = 'Failover'
                                    routing_details = f"Failover: {record['Failover']}, SetID: {record.get('SetIdentifier', 'N/A')}"
                                elif record.get('GeoLocation'):
                                    routing_policy = 'Geolocation'
                                    geo = record['GeoLocation']
                                    routing_details = f"Geo: {geo}, SetID: {record.get('SetIdentifier', 'N/A')}"
                                elif record.get('MultiValueAnswer'):
                                    routing_policy = 'Multivalue Answer'
                                    routing_details = f"SetID: {record.get('SetIdentifier', 'N/A')}"

                                # Health check
                                health_check_id = record.get('HealthCheckId', 'N/A')

                                record_data = {
                                    'Hosted Zone': zone_name,
                                    'Hosted Zone ID': zone_id.split('/')[-1],
                                    'Record Name': record_name,
                                    'Type': record_type,
                                    'TTL': ttl,
                                    'Value': record_value,
                                    'Routing Policy': routing_policy,
                                    'Routing Details': routing_details if routing_details else 'N/A',
                                    'Alias Target Zone ID': alias_zone_id,
                                    'Evaluate Target Health': evaluate_health,
                                    'Health Check ID': health_check_id
                                }

                                all_records.append(record_data)

                            except Exception as e:
                                utils.log_error(f"Error processing record in zone {zone_name}", e)
                                continue

                    time.sleep(0.2)  # Rate limiting between zones

                except Exception as e:
                    utils.log_error(f"Error collecting records for zone {zone_name}", e)
                    continue

        utils.log_success(f"Total DNS records collected: {len(all_records)}")

    except Exception as e:
        utils.log_error("Error collecting DNS records", e)

    return all_records

def collect_resolver_endpoints_data(regions):
    """
    Collect Route 53 Resolver endpoints information from specified regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with resolver endpoint information
    """
    print("\n=== COLLECTING RESOLVER ENDPOINTS INFORMATION ===")
    all_endpoints = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"  Scanning region: {region}")

        try:
            route53resolver_client = boto3.client('route53resolver', region_name=region)

            # Get all resolver endpoints
            paginator = route53resolver_client.get_paginator('list_resolver_endpoints')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                endpoints = page.get('ResolverEndpoints', [])

                for endpoint in endpoints:
                    try:
                        endpoint_id = endpoint.get('Id', 'N/A')
                        print(f"    Processing endpoint: {endpoint_id}")

                        # Get IP addresses for this endpoint
                        ip_addresses = []
                        try:
                            ip_paginator = route53resolver_client.get_paginator('list_resolver_endpoint_ip_addresses')
                            ip_iterator = ip_paginator.paginate(ResolverEndpointId=endpoint_id)

                            for ip_page in ip_iterator:
                                ip_addrs = ip_page.get('IpAddresses', [])
                                for ip_addr in ip_addrs:
                                    ip_addresses.append(
                                        f"{ip_addr.get('Ip', 'N/A')} (Subnet: {ip_addr.get('SubnetId', 'N/A')})"
                                    )
                        except Exception as e:
                            utils.log_warning(f"Could not retrieve IP addresses for endpoint {endpoint_id}: {e}")

                        endpoint_data = {
                            'Region': region,
                            'Resolver Endpoint ID': endpoint_id,
                            'Name': endpoint.get('Name', 'N/A'),
                            'Direction': endpoint.get('Direction', 'N/A'),
                            'Status': endpoint.get('Status', 'N/A'),
                            'IP Address Count': endpoint.get('IpAddressCount', 0),
                            'IP Addresses': ', '.join(ip_addresses) if ip_addresses else 'N/A',
                            'VPC ID': endpoint.get('HostVPCId', 'N/A'),
                            'Security Group IDs': ', '.join(endpoint.get('SecurityGroupIds', [])),
                            'Creation Time': str(endpoint.get('CreationTime', 'N/A')),
                            'Modification Time': str(endpoint.get('ModificationTime', 'N/A'))
                        }

                        all_endpoints.append(endpoint_data)
                        time.sleep(0.1)

                    except Exception as e:
                        utils.log_error(f"Error processing resolver endpoint {endpoint.get('Id', 'unknown')}", e)
                        continue

            time.sleep(0.3)  # Rate limiting between regions

        except Exception as e:
            utils.log_error(f"Error collecting resolver endpoints in region {region}", e)
            continue

    utils.log_success(f"Total resolver endpoints collected: {len(all_endpoints)}")
    return all_endpoints

def collect_resolver_rules_data(regions):
    """
    Collect Route 53 Resolver rules information from specified regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with resolver rule information
    """
    print("\n=== COLLECTING RESOLVER RULES INFORMATION ===")
    all_rules = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"  Scanning region: {region}")

        try:
            route53resolver_client = boto3.client('route53resolver', region_name=region)

            # Get all resolver rules
            paginator = route53resolver_client.get_paginator('list_resolver_rules')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                rules = page.get('ResolverRules', [])

                for rule in rules:
                    try:
                        rule_id = rule.get('Id', 'N/A')
                        print(f"    Processing rule: {rule_id}")

                        # Get target IPs for FORWARD rules
                        target_ips = []
                        if rule.get('RuleType') == 'FORWARD':
                            targets = rule.get('TargetIps', [])
                            for target in targets:
                                target_ips.append(f"{target.get('Ip', 'N/A')}:{target.get('Port', '53')}")

                        rule_data = {
                            'Region': region,
                            'Resolver Rule ID': rule_id,
                            'Name': rule.get('Name', 'N/A'),
                            'Domain Name': rule.get('DomainName', 'N/A'),
                            'Rule Type': rule.get('RuleType', 'N/A'),
                            'Target IPs': ', '.join(target_ips) if target_ips else 'N/A',
                            'Resolver Endpoint ID': rule.get('ResolverEndpointId', 'N/A'),
                            'Status': rule.get('Status', 'N/A'),
                            'Owner ID': rule.get('OwnerId', 'N/A'),
                            'Share Status': rule.get('ShareStatus', 'N/A'),
                            'Creation Time': str(rule.get('CreationTime', 'N/A')),
                            'Modification Time': str(rule.get('ModificationTime', 'N/A'))
                        }

                        all_rules.append(rule_data)
                        time.sleep(0.1)

                    except Exception as e:
                        utils.log_error(f"Error processing resolver rule {rule.get('Id', 'unknown')}", e)
                        continue

            time.sleep(0.3)  # Rate limiting between regions

        except Exception as e:
            utils.log_error(f"Error collecting resolver rules in region {region}", e)
            continue

    utils.log_success(f"Total resolver rules collected: {len(all_rules)}")
    return all_rules

def collect_resolver_rule_associations_data(regions):
    """
    Collect Route 53 Resolver rule associations with VPCs.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with rule association information
    """
    print("\n=== COLLECTING RESOLVER RULE ASSOCIATIONS ===")
    all_associations = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"  Scanning region: {region}")

        try:
            route53resolver_client = boto3.client('route53resolver', region_name=region)

            # Get all rule associations
            paginator = route53resolver_client.get_paginator('list_resolver_rule_associations')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                associations = page.get('ResolverRuleAssociations', [])

                for assoc in associations:
                    try:
                        assoc_data = {
                            'Region': region,
                            'Association ID': assoc.get('Id', 'N/A'),
                            'VPC ID': assoc.get('VPCId', 'N/A'),
                            'Resolver Rule ID': assoc.get('ResolverRuleId', 'N/A'),
                            'Name': assoc.get('Name', 'N/A'),
                            'Status': assoc.get('Status', 'N/A')
                        }

                        all_associations.append(assoc_data)

                    except Exception as e:
                        utils.log_error(f"Error processing rule association", e)
                        continue

            time.sleep(0.3)

        except Exception as e:
            utils.log_error(f"Error collecting rule associations in region {region}", e)
            continue

    utils.log_success(f"Total rule associations collected: {len(all_associations)}")
    return all_associations

def collect_query_logging_configs_data(regions):
    """
    Collect Route 53 query logging configurations.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with query logging configuration information
    """
    print("\n=== COLLECTING QUERY LOGGING CONFIGURATIONS ===")
    all_configs = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"  Scanning region: {region}")

        try:
            route53resolver_client = boto3.client('route53resolver', region_name=region)

            # Get all query logging configs
            paginator = route53resolver_client.get_paginator('list_resolver_query_log_configs')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                configs = page.get('ResolverQueryLogConfigs', [])

                for config in configs:
                    try:
                        # Get associated hosted zones
                        associations = []
                        try:
                            assoc_paginator = route53resolver_client.get_paginator('list_resolver_query_log_config_associations')
                            assoc_iterator = assoc_paginator.paginate(
                                Filters=[
                                    {
                                        'Name': 'ResolverQueryLogConfigId',
                                        'Values': [config['Id']]
                                    }
                                ]
                            )

                            for assoc_page in assoc_iterator:
                                assocs = assoc_page.get('ResolverQueryLogConfigAssociations', [])
                                for assoc in assocs:
                                    associations.append(assoc.get('ResourceId', 'N/A'))
                        except Exception as e:
                            utils.log_warning(f"Could not retrieve associations for query log config: {e}")

                        config_data = {
                            'Region': region,
                            'Query Log Config ID': config.get('Id', 'N/A'),
                            'Name': config.get('Name', 'N/A'),
                            'Destination ARN': config.get('DestinationArn', 'N/A'),
                            'Associated Resources': ', '.join(associations) if associations else 'N/A',
                            'Status': config.get('Status', 'N/A'),
                            'Owner ID': config.get('OwnerId', 'N/A'),
                            'Share Status': config.get('ShareStatus', 'N/A'),
                            'Creation Time': str(config.get('CreationTime', 'N/A'))
                        }

                        all_configs.append(config_data)
                        time.sleep(0.1)

                    except Exception as e:
                        utils.log_error(f"Error processing query logging config", e)
                        continue

            time.sleep(0.3)

        except Exception as e:
            utils.log_error(f"Error collecting query logging configs in region {region}", e)
            continue

    utils.log_success(f"Total query logging configs collected: {len(all_configs)}")
    return all_configs

def export_route53_info(account_id, account_name):
    """
    Export Route 53 information to an Excel file.

    Args:
        account_id: The AWS account ID
        account_name: The AWS account name
    """
    # Import pandas after dependency check
    import pandas as pd

    # Ask user which regions to scan for regional features (Resolver)
    print("\n" + "=" * 60)
    print("AWS Region Selection for Route 53 Resolver features:")
    print("(Note: Hosted zones and DNS records are global)")
    print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
    region_input = input("Would you like all AWS regions (type \"all\") or a specific region (ex. \"us-east-1\")? ").strip().lower()

    # Get available regions
    all_available_regions = utils.get_available_aws_regions()
    if not all_available_regions:
        all_available_regions = utils.get_aws_regions()

    # Determine regions to scan
    if region_input == "all":
        regions = all_available_regions
        region_text = "all AWS regions"
    else:
        if utils.validate_aws_region(region_input):
            regions = [region_input]
            region_text = f"AWS region {region_input}"
        else:
            utils.log_warning(f"'{region_input}' is not a valid AWS region. Using all AWS regions.")
            regions = all_available_regions
            region_text = "all AWS regions"

    # Create filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    region_suffix = "" if region_input == "all" else f"-{region_input}"

    final_excel_file = utils.create_export_filename(
        account_name,
        "route53",
        region_suffix,
        current_date
    )

    print(f"\nStarting AWS Route 53 export process...")
    print("This may take some time depending on the number of resources...")

    utils.log_info(f"Processing {len(regions)} AWS regions for regional features: {', '.join(regions)}")

    # Dictionary to hold all DataFrames
    data_frames = {}

    # STEP 1: Collect Hosted Zones (Global)
    hosted_zones_data = collect_hosted_zones_data()
    if hosted_zones_data:
        data_frames['Hosted Zones'] = pd.DataFrame(hosted_zones_data)

    # STEP 2: Collect DNS Record Sets (Global)
    record_sets_data = collect_record_sets_data()
    if record_sets_data:
        data_frames['DNS Records'] = pd.DataFrame(record_sets_data)

    # STEP 3: Collect Resolver Endpoints (Regional)
    resolver_endpoints_data = collect_resolver_endpoints_data(regions)
    if resolver_endpoints_data:
        data_frames['Resolver Endpoints'] = pd.DataFrame(resolver_endpoints_data)

    # STEP 4: Collect Resolver Rules (Regional)
    resolver_rules_data = collect_resolver_rules_data(regions)
    if resolver_rules_data:
        data_frames['Resolver Rules'] = pd.DataFrame(resolver_rules_data)

    # STEP 5: Collect Resolver Rule Associations (Regional)
    rule_associations_data = collect_resolver_rule_associations_data(regions)
    if rule_associations_data:
        data_frames['Resolver Rule Associations'] = pd.DataFrame(rule_associations_data)

    # STEP 6: Collect Query Logging Configurations (Regional)
    query_logging_data = collect_query_logging_configs_data(regions)
    if query_logging_data:
        data_frames['Query Logging Configs'] = pd.DataFrame(query_logging_data)

    # STEP 7: Create Summary
    summary_data = []
    summary_data.append({
        'Resource Type': 'Hosted Zones',
        'Count': len(hosted_zones_data)
    })
    summary_data.append({
        'Resource Type': 'DNS Records',
        'Count': len(record_sets_data)
    })
    summary_data.append({
        'Resource Type': 'Resolver Endpoints',
        'Count': len(resolver_endpoints_data)
    })
    summary_data.append({
        'Resource Type': 'Resolver Rules',
        'Count': len(resolver_rules_data)
    })
    summary_data.append({
        'Resource Type': 'Resolver Rule Associations',
        'Count': len(rule_associations_data)
    })
    summary_data.append({
        'Resource Type': 'Query Logging Configs',
        'Count': len(query_logging_data)
    })

    if summary_data:
        data_frames['Summary'] = pd.DataFrame(summary_data)

    # STEP 8: Save the Excel file
    if not data_frames:
        utils.log_warning("No data was collected. Nothing to export.")
        return

    try:
        output_path = utils.save_multiple_dataframes_to_excel(data_frames, final_excel_file)

        if output_path:
            utils.log_success("AWS Route 53 data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s) for regional features")

            # Summary of exported data
            for sheet_name, df in data_frames.items():
                utils.log_info(f"  - {sheet_name}: {len(df)} records")
        else:
            utils.log_error("Error creating Excel file. Please check the logs.")

    except Exception as e:
        utils.log_error(f"Error creating Excel file", e)

def main():
    """Main function to execute the script."""
    try:
        # Print title and get account information
        account_id, account_name = print_title()

        # Check and install dependencies
        check_and_install_dependencies()

        # Check if account name is unknown
        if account_name == "unknown":
            proceed = input("Unable to determine account name. Proceed anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Exiting script...")
                sys.exit(0)

        # Export Route 53 information
        export_route53_info(account_id, account_name)

        print("\nAWS Route 53 data export script execution completed.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        utils.log_error("An unexpected error occurred", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
