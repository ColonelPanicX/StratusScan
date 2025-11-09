#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Transit Gateway Export Tool
Version: v1.0.0
Date: NOV-09-2025

Description:
This script exports AWS Transit Gateway information from all regions into an Excel file with
multiple worksheets. The output includes Transit Gateway configurations, attachments,
route tables, routes, and peering connections.

Features:
- Transit Gateway overview with configurations and state
- VPC attachments with association details
- VPN attachments
- Direct Connect Gateway attachments
- Peering attachments (inter-region and cross-account)
- Route tables and propagations
- Route entries with CIDR blocks and attachment targets
- Resource sharing information
"""

import sys
import datetime
from pathlib import Path
from typing import List, Dict, Any

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

# Initialize logging
SCRIPT_START_TIME = datetime.datetime.now()
utils.setup_logging("transit-gateway-export")
utils.log_script_start("transit-gateway-export.py", "AWS Transit Gateway Export Tool")


def print_title():
    """Print the title and header of the script to the console."""
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                    ")
    print("====================================================================")
    print("             AWS TRANSIT GATEWAY EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.0.0                        Date: NOV-09-2025")
    print("Environment: AWS Commercial")
    print("====================================================================")

    # Get the current AWS account ID
    try:
        sts_client = utils.get_boto3_client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_name = utils.get_account_name(account_id, default=account_id)

        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print("Could not determine account information.")
        utils.log_error("Error getting account information", e)
        account_id = "unknown"
        account_name = "unknown"

    print("====================================================================")
    return account_id, account_name


def get_aws_regions():
    """Get a list of available AWS regions."""
    try:
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_default_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        return utils.get_default_regions()


@utils.aws_error_handler("Collecting Transit Gateways", default_return=[])
def collect_transit_gateways(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect Transit Gateway information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with Transit Gateway information
    """
    print("\n=== COLLECTING TRANSIT GATEWAYS ===")
    all_tgws = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"\nProcessing region: {region}")

        try:
            ec2 = utils.get_boto3_client('ec2', region_name=region)

            # Get Transit Gateways in the region
            paginator = ec2.get_paginator('describe_transit_gateways')
            tgw_count = 0

            for page in paginator.paginate():
                tgws = page.get('TransitGateways', [])
                tgw_count += len(tgws)

                for tgw in tgws:
                    tgw_id = tgw.get('TransitGatewayId', '')
                    print(f"  Processing Transit Gateway: {tgw_id}")

                    # Extract basic information
                    state = tgw.get('State', '')
                    description = tgw.get('Description', 'N/A')
                    owner_id = tgw.get('OwnerId', '')
                    owner_name = utils.get_account_name_formatted(owner_id)

                    # Creation time
                    creation_time = tgw.get('CreationTime', '')
                    if creation_time:
                        creation_time = creation_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(creation_time, datetime.datetime) else str(creation_time)

                    # Options
                    options = tgw.get('Options', {})
                    amazon_side_asn = options.get('AmazonSideAsn', 'N/A')
                    default_route_table_association = options.get('DefaultRouteTableAssociation', 'N/A')
                    default_route_table_propagation = options.get('DefaultRouteTablePropagation', 'N/A')
                    vpn_ecmp_support = options.get('VpnEcmpSupport', 'N/A')
                    dns_support = options.get('DnsSupport', 'N/A')
                    auto_accept_shared_attachments = options.get('AutoAcceptSharedAttachments', 'N/A')
                    multicast_support = options.get('MulticastSupport', 'N/A')

                    # Default route table IDs
                    association_default_rt = options.get('AssociationDefaultRouteTableId', 'N/A')
                    propagation_default_rt = options.get('PropagationDefaultRouteTableId', 'N/A')

                    # CIDR blocks
                    transit_gateway_cidr_blocks = options.get('TransitGatewayCidrBlocks', [])
                    cidr_blocks_str = ', '.join(transit_gateway_cidr_blocks) if transit_gateway_cidr_blocks else 'N/A'

                    # Get tags
                    tags = tgw.get('Tags', [])
                    name_tag = 'N/A'
                    for tag in tags:
                        if tag['Key'] == 'Name':
                            name_tag = tag['Value']
                            break

                    all_tgws.append({
                        'Region': region,
                        'Transit Gateway ID': tgw_id,
                        'Name': name_tag,
                        'State': state,
                        'Description': description,
                        'Owner Account': owner_name,
                        'Amazon Side ASN': amazon_side_asn,
                        'CIDR Blocks': cidr_blocks_str,
                        'Default Route Table Association': default_route_table_association,
                        'Default Route Table Propagation': default_route_table_propagation,
                        'Association Default RT ID': association_default_rt,
                        'Propagation Default RT ID': propagation_default_rt,
                        'VPN ECMP Support': vpn_ecmp_support,
                        'DNS Support': dns_support,
                        'Auto Accept Shared Attachments': auto_accept_shared_attachments,
                        'Multicast Support': multicast_support,
                        'Creation Time': creation_time
                    })

            print(f"  Found {tgw_count} Transit Gateways")

        except Exception as e:
            utils.log_error(f"Error processing region {region} for Transit Gateways", e)

    utils.log_success(f"Total Transit Gateways collected: {len(all_tgws)}")
    return all_tgws


@utils.aws_error_handler("Collecting Transit Gateway attachments", default_return=[])
def collect_transit_gateway_attachments(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect Transit Gateway attachment information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with attachment information
    """
    print("\n=== COLLECTING TRANSIT GATEWAY ATTACHMENTS ===")
    all_attachments = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"\nProcessing region: {region}")

        try:
            ec2 = utils.get_boto3_client('ec2', region_name=region)

            # Get Transit Gateway attachments
            paginator = ec2.get_paginator('describe_transit_gateway_attachments')
            attachment_count = 0

            for page in paginator.paginate():
                attachments = page.get('TransitGatewayAttachments', [])
                attachment_count += len(attachments)

                for attachment in attachments:
                    attachment_id = attachment.get('TransitGatewayAttachmentId', '')
                    tgw_id = attachment.get('TransitGatewayId', '')
                    resource_type = attachment.get('ResourceType', '')

                    print(f"  Processing attachment: {attachment_id} ({resource_type})")

                    # Extract basic information
                    state = attachment.get('State', '')
                    resource_id = attachment.get('ResourceId', 'N/A')
                    resource_owner_id = attachment.get('ResourceOwnerId', '')
                    resource_owner_name = utils.get_account_name_formatted(resource_owner_id)
                    tgw_owner_id = attachment.get('TransitGatewayOwnerId', '')
                    tgw_owner_name = utils.get_account_name_formatted(tgw_owner_id)

                    # Creation time
                    creation_time = attachment.get('CreationTime', '')
                    if creation_time:
                        creation_time = creation_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(creation_time, datetime.datetime) else str(creation_time)

                    # Association
                    association = attachment.get('Association', {})
                    route_table_id = association.get('TransitGatewayRouteTableId', 'N/A')
                    association_state = association.get('State', 'N/A')

                    # Get tags
                    tags = attachment.get('Tags', [])
                    name_tag = 'N/A'
                    for tag in tags:
                        if tag['Key'] == 'Name':
                            name_tag = tag['Value']
                            break

                    all_attachments.append({
                        'Region': region,
                        'Attachment ID': attachment_id,
                        'Name': name_tag,
                        'Transit Gateway ID': tgw_id,
                        'Resource Type': resource_type,
                        'Resource ID': resource_id,
                        'State': state,
                        'Resource Owner': resource_owner_name,
                        'TGW Owner': tgw_owner_name,
                        'Route Table ID': route_table_id,
                        'Association State': association_state,
                        'Creation Time': creation_time
                    })

            print(f"  Found {attachment_count} attachments")

        except Exception as e:
            utils.log_error(f"Error processing region {region} for attachments", e)

    utils.log_success(f"Total attachments collected: {len(all_attachments)}")
    return all_attachments


@utils.aws_error_handler("Collecting Transit Gateway route tables", default_return=[])
def collect_transit_gateway_route_tables(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect Transit Gateway route table information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with route table information
    """
    print("\n=== COLLECTING TRANSIT GATEWAY ROUTE TABLES ===")
    all_route_tables = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"\nProcessing region: {region}")

        try:
            ec2 = utils.get_boto3_client('ec2', region_name=region)

            # Get Transit Gateway route tables
            paginator = ec2.get_paginator('describe_transit_gateway_route_tables')
            rt_count = 0

            for page in paginator.paginate():
                route_tables = page.get('TransitGatewayRouteTables', [])
                rt_count += len(route_tables)

                for rt in route_tables:
                    rt_id = rt.get('TransitGatewayRouteTableId', '')
                    tgw_id = rt.get('TransitGatewayId', '')

                    print(f"  Processing route table: {rt_id}")

                    # Extract basic information
                    state = rt.get('State', '')
                    default_association_rt = rt.get('DefaultAssociationRouteTable', False)
                    default_propagation_rt = rt.get('DefaultPropagationRouteTable', False)

                    # Creation time
                    creation_time = rt.get('CreationTime', '')
                    if creation_time:
                        creation_time = creation_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(creation_time, datetime.datetime) else str(creation_time)

                    # Get tags
                    tags = rt.get('Tags', [])
                    name_tag = 'N/A'
                    for tag in tags:
                        if tag['Key'] == 'Name':
                            name_tag = tag['Value']
                            break

                    all_route_tables.append({
                        'Region': region,
                        'Route Table ID': rt_id,
                        'Name': name_tag,
                        'Transit Gateway ID': tgw_id,
                        'State': state,
                        'Default Association RT': default_association_rt,
                        'Default Propagation RT': default_propagation_rt,
                        'Creation Time': creation_time
                    })

            print(f"  Found {rt_count} route tables")

        except Exception as e:
            utils.log_error(f"Error processing region {region} for route tables", e)

    utils.log_success(f"Total route tables collected: {len(all_route_tables)}")
    return all_route_tables


@utils.aws_error_handler("Collecting Transit Gateway routes", default_return=[])
def collect_transit_gateway_routes(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect Transit Gateway route information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with route information
    """
    print("\n=== COLLECTING TRANSIT GATEWAY ROUTES ===")
    all_routes = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"\nProcessing region: {region}")

        try:
            ec2 = utils.get_boto3_client('ec2', region_name=region)

            # First get all route tables
            paginator = ec2.get_paginator('describe_transit_gateway_route_tables')

            for page in paginator.paginate():
                route_tables = page.get('TransitGatewayRouteTables', [])

                for rt in route_tables:
                    rt_id = rt.get('TransitGatewayRouteTableId', '')
                    tgw_id = rt.get('TransitGatewayId', '')

                    print(f"  Searching routes in route table: {rt_id}")

                    try:
                        # Get routes for this route table
                        routes_response = ec2.search_transit_gateway_routes(
                            TransitGatewayRouteTableId=rt_id,
                            Filters=[
                                {
                                    'Name': 'state',
                                    'Values': ['active', 'blackhole']
                                }
                            ]
                        )

                        routes = routes_response.get('Routes', [])

                        for route in routes:
                            destination_cidr = route.get('DestinationCidrBlock', 'N/A')
                            route_type = route.get('Type', '')
                            state = route.get('State', '')

                            # Get attachment information
                            attachments = route.get('TransitGatewayAttachments', [])
                            if attachments:
                                for att in attachments:
                                    attachment_id = att.get('TransitGatewayAttachmentId', 'N/A')
                                    resource_id = att.get('ResourceId', 'N/A')
                                    resource_type = att.get('ResourceType', 'N/A')

                                    all_routes.append({
                                        'Region': region,
                                        'Route Table ID': rt_id,
                                        'Transit Gateway ID': tgw_id,
                                        'Destination CIDR': destination_cidr,
                                        'Type': route_type,
                                        'State': state,
                                        'Attachment ID': attachment_id,
                                        'Resource Type': resource_type,
                                        'Resource ID': resource_id
                                    })
                            else:
                                # Route without attachment (e.g., blackhole)
                                all_routes.append({
                                    'Region': region,
                                    'Route Table ID': rt_id,
                                    'Transit Gateway ID': tgw_id,
                                    'Destination CIDR': destination_cidr,
                                    'Type': route_type,
                                    'State': state,
                                    'Attachment ID': 'N/A',
                                    'Resource Type': 'N/A',
                                    'Resource ID': 'N/A'
                                })

                    except Exception as e:
                        utils.log_error(f"Error getting routes for route table {rt_id}", e)

        except Exception as e:
            utils.log_error(f"Error processing region {region} for routes", e)

    utils.log_success(f"Total routes collected: {len(all_routes)}")
    return all_routes


def export_transit_gateway_data(account_id: str, account_name: str):
    """
    Export Transit Gateway information to an Excel file.

    Args:
        account_id: The AWS account ID
        account_name: The AWS account name
    """
    # Ask for region selection
    print("\n" + "=" * 60)
    print("AWS Region Selection:")
    print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1")
    region_input = input("Would you like all AWS regions (type \"all\") or a specific region (ex. \"us-east-1\")? ").strip().lower()

    # Get all available AWS regions
    all_available_regions = get_aws_regions()

    # Determine regions to scan
    if region_input == "all":
        regions = all_available_regions
        region_text = "all AWS regions"
        region_suffix = ""
    else:
        # Validate the provided region
        if utils.validate_aws_region(region_input):
            regions = [region_input]
            region_text = f"AWS region {region_input}"
            region_suffix = f"-{region_input}"
        else:
            utils.log_warning(f"'{region_input}' is not a valid AWS region. Using all AWS regions.")
            regions = all_available_regions
            region_text = "all AWS regions"
            region_suffix = ""

    print(f"\nStarting Transit Gateway export process for {region_text}...")
    print("This may take some time depending on the number of regions and resources...")

    utils.log_info(f"Processing {len(regions)} AWS regions: {', '.join(regions)}")

    # Import pandas for DataFrame handling
    import pandas as pd

    # Dictionary to hold all DataFrames for export
    data_frames = {}

    # STEP 1: Collect Transit Gateways
    tgws = collect_transit_gateways(regions)
    if tgws:
        data_frames['Transit Gateways'] = pd.DataFrame(tgws)

    # STEP 2: Collect attachments
    attachments = collect_transit_gateway_attachments(regions)
    if attachments:
        data_frames['Attachments'] = pd.DataFrame(attachments)

    # STEP 3: Collect route tables
    route_tables = collect_transit_gateway_route_tables(regions)
    if route_tables:
        data_frames['Route Tables'] = pd.DataFrame(route_tables)

    # STEP 4: Collect routes
    routes = collect_transit_gateway_routes(regions)
    if routes:
        data_frames['Routes'] = pd.DataFrame(routes)

    # Check if we have any data
    if not data_frames:
        utils.log_warning("No Transit Gateway data was collected. Nothing to export.")
        print("\nNo Transit Gateways found in the selected region(s).")
        return

    # STEP 5: Prepare all DataFrames for export
    for sheet_name in data_frames:
        data_frames[sheet_name] = utils.prepare_dataframe_for_export(data_frames[sheet_name])

    # STEP 6: Create filename and export
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    final_excel_file = utils.create_export_filename(
        account_name,
        'transit-gateway',
        region_suffix,
        current_date
    )

    # Save using utils module for consistent formatting
    try:
        output_path = utils.save_multiple_dataframes_to_excel(data_frames, final_excel_file)

        if output_path:
            utils.log_success("Transit Gateway data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")

            # Summary of exported data
            for sheet_name, df in data_frames.items():
                utils.log_info(f"  - {sheet_name}: {len(df)} records")
                print(f"  - {sheet_name}: {len(df)} records")
        else:
            utils.log_error("Error creating Excel file. Please check the logs.")

    except Exception as e:
        utils.log_error("Error creating Excel file", e)


def main():
    """Main function to execute the script."""
    try:
        # Print title and get account information
        account_id, account_name = print_title()

        # Check and install dependencies
        if not utils.ensure_dependencies('pandas', 'openpyxl'):
            sys.exit(1)

        # Check if account name is unknown
        if account_name == "unknown":
            proceed = input("Unable to determine account name. Proceed anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Exiting script...")
                sys.exit(0)

        # Export Transit Gateway data
        export_transit_gateway_data(account_id, account_name)

        print("\nTransit Gateway export script execution completed.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        utils.log_info("Script cancelled by user")
        sys.exit(1)
    except Exception as e:
        utils.log_error("An unexpected error occurred", e)
        sys.exit(1)
    finally:
        utils.log_script_end("transit-gateway-export.py", SCRIPT_START_TIME)


if __name__ == "__main__":
    main()
