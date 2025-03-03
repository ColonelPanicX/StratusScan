#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS VPC, Subnet, NAT Gateway, Peering Connection, and Elastic IP Export Tool
Version: v1.4.0
Date: FEB-27-2025

Description:
This script exports VPC, subnet, NAT Gateway, VPC Peering Connection, and Elastic IP information 
from all AWS regions or a specific region into an Excel file with separate worksheets. The output 
filename includes the AWS account name based on the account ID mapping in the configuration.
"""

import os
import sys
import csv
import json
import datetime
import time
import boto3
from botocore.exceptions import ClientError
from time import sleep
from pathlib import Path

# Add path to import utils module
try:
    # Try to import directly (if utils.py is in Python path)
    import utils
except ImportError:
    # If import fails, try to find the module relative to this script
    script_dir = Path(__file__).parent.absolute()
    
    # Check if we're in the scripts directory
    if script_dir.name.lower() == 'scripts':
        # Add the parent directory (StratusScan root) to the path
        sys.path.append(str(script_dir.parent))
    else:
        # Add the current directory to the path
        sys.path.append(str(script_dir))
    
    # Try import again
    try:
        import utils
    except ImportError:
        print("ERROR: Could not import the utils module. Make sure utils.py is in the StratusScan directory.")
        sys.exit(1)

def print_title():
    """Print the title and header of the script to the console."""
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS VPC, SUBNET, NAT GATEWAY, PEERING, AND ELASTIC IP EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.4.0                                 Date: FEB-27-2025")
    print("====================================================================")
    
    # Get the current AWS account ID
    try:
        # Create a new STS client to get the current account ID
        sts_client = boto3.client('sts')
        # Call get-caller-identity to retrieve the account ID
        account_id = sts_client.get_caller_identity().get('Account')
        # Map the account ID to an account name, or use the ID if no mapping exists
        account_name = utils.get_account_name(account_id, default=account_id)
        
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print("Could not determine account information.")
        account_id = "unknown"
        account_name = "unknown"
    
    print("====================================================================")
    return account_id, account_name

def check_and_install_dependencies():
    """Check and install required dependencies if needed."""
    required_packages = ['pandas', 'openpyxl']
    
    for package in required_packages:
        try:
            # Try to import the package to check if it's installed
            __import__(package)
            print(f"{package} is already installed.")
        except ImportError:
            # If import fails, offer to install the package
            response = input(f"{package} is not installed. Do you want to install it? (y/n): ")
            if response.lower() == 'y':
                print(f"Installing {package}...")
                os.system(f"pip install {package}")
                print(f"{package} has been installed.")
            else:
                print(f"Skipping installation of {package}.")
                print(f"Note: The script may not function correctly without {package}.")

def get_all_regions():
    """Get a list of all available AWS regions."""
    try:
        # Create a new EC2 client to get the list of regions
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        # Describe all available regions
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error retrieving AWS regions: {e}")
        # Return a default list of common regions if we can't get the full list
        return ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'eu-west-1', 'eu-central-1']

def is_subnet_public(ec2_client, subnet_id, vpc_id):
    """
    Determine if a subnet is public by checking if it has a route to an Internet Gateway.
    
    Args:
        ec2_client: The boto3 EC2 client
        subnet_id: The ID of the subnet to check
        vpc_id: The ID of the VPC the subnet belongs to
        
    Returns:
        bool: True if the subnet is public, False otherwise
    """
    try:
        # Get the route tables associated with the subnet
        response = ec2_client.describe_route_tables(
            Filters=[
                {
                    'Name': 'association.subnet-id',
                    'Values': [subnet_id]
                }
            ]
        )
        
        # If there are explicit route table associations for this subnet
        route_tables = response.get('RouteTables', [])
        
        # If no explicit route table associated, get the main route table for the VPC
        if not route_tables:
            response = ec2_client.describe_route_tables(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [vpc_id]
                    },
                    {
                        'Name': 'association.main',
                        'Values': ['true']
                    }
                ]
            )
            route_tables = response.get('RouteTables', [])
        
        # Check if any route table has a route to an IGW
        for rt in route_tables:
            for route in rt.get('Routes', []):
                # Check for a default route (0.0.0.0/0) pointing to an IGW
                if route.get('DestinationCidrBlock') == '0.0.0.0/0' and 'GatewayId' in route and route['GatewayId'].startswith('igw-'):
                    return True
        
        # If we get here, no route to IGW was found
        return False
    except Exception as e:
        print(f"Error checking if subnet {subnet_id} is public: {e}")
        return "Unknown"

def collect_vpc_subnet_data(regions):
    """
    Collect VPC and subnet information from all regions.
    
    Args:
        regions: List of AWS regions to scan
        
    Returns:
        list: List of dictionaries with subnet information
    """
    print("\n=== COLLECTING VPC AND SUBNET INFORMATION ===")
    all_subnet_data = []
    
    # Process each region
    for region in regions:
        print(f"\nProcessing region: {region}")
        
        try:
            # Create EC2 client for this region
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Get all VPCs in the region
            vpc_response = ec2_client.describe_vpcs()
            vpcs = vpc_response.get('Vpcs', [])
            
            print(f"Found {len(vpcs)} VPCs in region {region}")
            
            # Process each VPC
            for vpc in vpcs:
                vpc_id = vpc['VpcId']
                print(f"  Processing VPC: {vpc_id}")
                
                # Get all subnets for this VPC
                subnet_response = ec2_client.describe_subnets(
                    Filters=[
                        {
                            'Name': 'vpc-id',
                            'Values': [vpc_id]
                        }
                    ]
                )
                subnets = subnet_response.get('Subnets', [])
                
                print(f"    Found {len(subnets)} subnets")
                
                # Process each subnet
                for subnet in subnets:
                    subnet_id = subnet['SubnetId']
                    
                    # Extract subnet name from tags
                    subnet_name = None
                    if 'Tags' in subnet:
                        for tag in subnet['Tags']:
                            if tag['Key'] == 'Name':
                                subnet_name = tag['Value']
                                break
                    
                    availability_zone = subnet['AvailabilityZone']
                    ipv4_cidr = subnet['CidrBlock']
                    ipv4_address_count = subnet.get('AvailableIpAddressCount', 'N/A')
                    
                    # Get IPv6 CIDR if available
                    ipv6_cidr = 'N/A'
                    if 'Ipv6CidrBlockAssociationSet' in subnet and subnet['Ipv6CidrBlockAssociationSet']:
                        for ipv6_assoc in subnet['Ipv6CidrBlockAssociationSet']:
                            if ipv6_assoc.get('Ipv6CidrBlockState', {}).get('State') == 'associated':
                                ipv6_cidr = ipv6_assoc.get('Ipv6CidrBlock', 'N/A')
                                break
                    
                    # Determine if subnet is public or private
                    public_status = is_subnet_public(ec2_client, subnet_id, vpc_id)
                    public_private = "Public" if public_status else "Private"
                    
                    # Append subnet data to the list
                    subnet_data = {
                        'Region': region,
                        'VPC ID': vpc_id,
                        'Subnet ID': subnet_id,
                        'Subnet Name': subnet_name if subnet_name else 'N/A',
                        'Availability Zone': availability_zone,
                        'IPv4 CIDR Block': ipv4_cidr,
                        'IPv4 Address Count': ipv4_address_count,
                        'IPv6 CIDR Block': ipv6_cidr,
                        'Public/Private': public_private
                    }
                    all_subnet_data.append(subnet_data)
        
        except Exception as e:
            print(f"Error processing region {region} for VPCs/Subnets: {e}")
            continue
    
    print(f"\nTotal subnets collected: {len(all_subnet_data)}")
    return all_subnet_data

def collect_nat_gateway_data(regions):
    """
    Collect NAT Gateway information from all regions.
    
    Args:
        regions: List of AWS regions to scan
        
    Returns:
        list: List of dictionaries with NAT Gateway information
    """
    print("\n=== COLLECTING NAT GATEWAY INFORMATION ===")
    all_nat_gateways = []
    
    # Process each region for NAT Gateways
    for region in regions:
        print(f"\nSearching for NAT Gateways in region: {region}")
        
        try:
            # Create EC2 client for this region
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Get NAT Gateways in the region
            try:
                nat_gw_response = ec2_client.describe_nat_gateways()
                nat_gws = nat_gw_response.get('NatGateways', [])
                print(f"  Found {len(nat_gws)} NAT Gateways")
                
                # Process each NAT Gateway
                for nat_gw in nat_gws:
                    try:
                        nat_gw_id = nat_gw.get('NatGatewayId', '')
                        print(f"    Processing NAT Gateway: {nat_gw_id}")
                        
                        state = nat_gw.get('State', '')
                        connectivity = nat_gw.get('ConnectivityType', '')
                        vpc_id = nat_gw.get('VpcId', '')
                        subnet_id = nat_gw.get('SubnetId', '')
                        
                        # Get creation timestamp and format it
                        creation_timestamp = nat_gw.get('CreateTime', '')
                        if creation_timestamp:
                            try:
                                # Convert to datetime object and then to string format
                                creation_date = creation_timestamp.strftime('%Y-%m-%d') if isinstance(creation_timestamp, datetime.datetime) else str(creation_timestamp)
                            except Exception as e:
                                print(f"      Error formatting date: {str(e)}")
                                creation_date = str(creation_timestamp)
                        else:
                            creation_date = ""
                        
                        # Extract name from tags
                        name = None
                        if 'Tags' in nat_gw:
                            for tag in nat_gw['Tags']:
                                if tag['Key'] == 'Name':
                                    name = tag['Value']
                                    break
                        
                        # Get primary network interface details
                        primary_public_ip = ""
                        primary_private_ip = ""
                        primary_eni_id = ""
                        
                        nat_addresses = nat_gw.get('NatGatewayAddresses', [])
                        if nat_addresses:
                            primary_nat_address = nat_addresses[0]
                            primary_public_ip = primary_nat_address.get('PublicIp', '')
                            primary_private_ip = primary_nat_address.get('PrivateIp', '')
                            primary_eni_id = primary_nat_address.get('NetworkInterfaceId', '')
                        
                        # Add to results
                        all_nat_gateways.append({
                            'Region': region,
                            'Name': name if name else 'N/A',
                            'NAT Gateway ID': nat_gw_id,
                            'State': state,
                            'Connectivity': connectivity,
                            'Primary Public IPv4': primary_public_ip,
                            'Primary Private IPv4': primary_private_ip,
                            'Primary Network Interface ID': primary_eni_id,
                            'VPC': vpc_id,
                            'Subnet': subnet_id,
                            'Creation Date': creation_date
                        })
                    except Exception as e:
                        print(f"      Error processing NAT Gateway {nat_gw_id}: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"  Error retrieving NAT Gateways in region {region}: {str(e)}")
        
        except Exception as e:
            print(f"Error processing region {region} for NAT Gateways: {e}")
            continue
        
        # Add a small delay to avoid API throttling
        sleep(0.5)
    
    print(f"\nTotal NAT Gateways collected: {len(all_nat_gateways)}")
    return all_nat_gateways

def collect_vpc_peering_data(regions):
    """
    Collect VPC Peering Connection information from all regions.
    
    Args:
        regions: List of AWS regions to scan
        
    Returns:
        list: List of dictionaries with VPC Peering information
    """
    print("\n=== COLLECTING VPC PEERING CONNECTION INFORMATION ===")
    all_vpc_peerings = []
    
    # Process each region for VPC Peering Connections
    for region in regions:
        print(f"\nSearching for VPC Peering Connections in region: {region}")
        
        try:
            # Create EC2 client for this region
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Get VPC Peering Connections in the region
            try:
                peering_response = ec2_client.describe_vpc_peering_connections()
                peerings = peering_response.get('VpcPeeringConnections', [])
                print(f"  Found {len(peerings)} VPC Peering Connections")
                
                # Process each VPC Peering Connection
                for peering in peerings:
                    try:
                        peering_id = peering.get('VpcPeeringConnectionId', '')
                        print(f"    Processing VPC Peering Connection: {peering_id}")
                        
                        # Get peering status
                        status = peering.get('Status', {}).get('Code', '')
                        
                        # Get requester VPC information
                        requester_info = peering.get('RequesterVpcInfo', {})
                        requester_vpc = requester_info.get('VpcId', '')
                        requester_cidr = requester_info.get('CidrBlock', '')
                        requester_owner = requester_info.get('OwnerId', '')
                        requester_region = requester_info.get('Region', '')
                        
                        # Get accepter VPC information
                        accepter_info = peering.get('AccepterVpcInfo', {})
                        accepter_vpc = accepter_info.get('VpcId', '')
                        accepter_cidr = accepter_info.get('CidrBlock', '')
                        accepter_owner = accepter_info.get('OwnerId', '')
                        accepter_region = accepter_info.get('Region', '')
                        
                        # Format account owner IDs with names if available
                        requester_owner_formatted = utils.get_account_name_formatted(requester_owner)
                        accepter_owner_formatted = utils.get_account_name_formatted(accepter_owner)
                        
                        # Extract name from tags
                        name = None
                        if 'Tags' in peering:
                            for tag in peering['Tags']:
                                if tag['Key'] == 'Name':
                                    name = tag['Value']
                                    break
                        
                        # Add to results
                        all_vpc_peerings.append({
                            'Name': name if name else 'N/A',
                            'Peering Connection ID': peering_id,
                            'Status': status,
                            'Requester VPC': requester_vpc,
                            'Accepter VPC': accepter_vpc,
                            'Requester CIDR': requester_cidr,
                            'Accepter CIDR': accepter_cidr,
                            'Requester Owner ID': requester_owner_formatted,
                            'Accepter Owner ID': accepter_owner_formatted,
                            'Requester Region': requester_region,
                            'Accepter Region': accepter_region
                        })
                    except Exception as e:
                        print(f"      Error processing VPC Peering Connection {peering_id}: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"  Error retrieving VPC Peering Connections in region {region}: {str(e)}")
        
        except Exception as e:
            print(f"Error processing region {region} for VPC Peering Connections: {e}")
            continue
        
        # Add a small delay to avoid API throttling
        sleep(0.5)
    
    print(f"\nTotal VPC Peering Connections collected: {len(all_vpc_peerings)}")
    return all_vpc_peerings

def collect_elastic_ip_data(regions):
    """
    Collect Elastic IP information from all regions.
    
    Args:
        regions: List of AWS regions to scan
        
    Returns:
        list: List of dictionaries with Elastic IP information
    """
    print("\n=== COLLECTING ELASTIC IP INFORMATION ===")
    all_elastic_ips = []
    
    # Process each region for Elastic IPs
    for region in regions:
        print(f"\nSearching for Elastic IPs in region: {region}")
        
        try:
            # Create EC2 client for this region
            ec2_client = boto3.client('ec2', region_name=region)
            
            # Get Elastic IPs in the region
            try:
                eip_response = ec2_client.describe_addresses()
                eips = eip_response.get('Addresses', [])
                print(f"  Found {len(eips)} Elastic IPs")
                
                # Process each Elastic IP
                for eip in eips:
                    try:
                        allocated_ip = eip.get('PublicIp', '')
                        print(f"    Processing Elastic IP: {allocated_ip}")
                        
                        # Get EIP attributes
                        allocation_id = eip.get('AllocationId', '')
                        domain_type = eip.get('Domain', '')  # 'vpc' or 'standard'
                        
                        # Get associated information if available
                        instance_id = eip.get('InstanceId', '')
                        private_ip = eip.get('PrivateIpAddress', '')
                        association_id = eip.get('AssociationId', '')
                        network_interface_id = eip.get('NetworkInterfaceId', '')
                        network_interface_owner_id = eip.get('NetworkInterfaceOwnerId', '')
                        network_border_group = eip.get('NetworkBorderGroup', '')
                        
                        # Get Public DNS (Reverse DNS record)
                        public_dns = eip.get('PublicDnsName', '')
                        
                        # Extract name from tags
                        name = None
                        if 'Tags' in eip:
                            for tag in eip['Tags']:
                                if tag['Key'] == 'Name':
                                    name = tag['Value']
                                    break
                        
                        # Add to results
                        all_elastic_ips.append({
                            'Region': region,
                            'Name': name if name else 'N/A',
                            'Allocated IPv4': allocated_ip,
                            'Type': domain_type,
                            'Allocation ID': allocation_id,
                            'Reverse DNS Record': public_dns,
                            'Associated Instance ID': instance_id,
                            'Private IPv4': private_ip,
                            'Association ID': association_id,
                            'Network Interface Owner ID': network_interface_owner_id,
                            'Network Border Group': network_border_group
                        })
                    except Exception as e:
                        print(f"      Error processing Elastic IP {allocated_ip}: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"  Error retrieving Elastic IPs in region {region}: {str(e)}")
        
        except Exception as e:
            print(f"Error processing region {region} for Elastic IPs: {e}")
            continue
        
        # Add a small delay to avoid API throttling
        sleep(0.5)
    
    print(f"\nTotal Elastic IPs collected: {len(all_elastic_ips)}")
    return all_elastic_ips

def export_vpc_subnet_natgw_peering_info(account_id, account_name):
    """
    Export VPC, subnet, NAT Gateway, VPC Peering, and Elastic IP information to an Excel file.
    Uses temporary CSV files for reliable processing.
    
    Args:
        account_id: The AWS account ID
        account_name: The AWS account name
    """
    # Display menu for user selection
    print("\n" + "=" * 60)
    print("What would you like to export?")
    print("1. VPC and Subnet")
    print("2. NAT Gateways")
    print("3. VPC Peering Connections")
    print("4. Elastic IP")
    print("5. All of the Above")
    print("=" * 60)
    
    # Get user selection
    while True:
        try:
            choice = input("Enter your choice (1-5): ")
            choice = int(choice)
            if 1 <= choice <= 5:
                break
            else:
                print("Please enter a number between 1 and 5.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Determine what to export based on user choice
    export_vpc_subnet = choice in [1, 5]
    export_nat_gateways = choice in [2, 5]
    export_vpc_peering = choice in [3, 5]
    export_elastic_ip = choice in [4, 5]
    
    # Ask for region selection
    print("\n" + "=" * 60)
    region_input = input("Would you like all regions (type \"all\") or a specific region (ex. \"us-east-1\")? ").strip().lower()
    
    # Get all available regions
    all_available_regions = get_all_regions()
    
    # Determine regions to scan
    if region_input == "all":
        regions = all_available_regions
        region_text = "all regions"
    else:
        # Validate the provided region
        if region_input in all_available_regions:
            regions = [region_input]
            region_text = f"region {region_input}"
        else:
            print(f"Warning: '{region_input}' does not appear to be a valid region. Defaulting to all regions.")
            regions = all_available_regions
            region_text = "all regions"
    
    # Get current date for file naming
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create appropriate filename based on selection and region
    region_suffix = "" if region_input == "all" else f"-{region_input}"
    
    if choice == 1:
        resource_type = "vpc-subnet"
    elif choice == 2:
        resource_type = "ngw"
    elif choice == 3:
        resource_type = "vpc-peering"
    elif choice == 4:
        resource_type = "elastic-ip"
    else:  # choice == 5
        resource_type = "vpc-all"
    
    # Create filename using utils
    final_excel_file = utils.create_export_filename(
        account_name, 
        resource_type, 
        region_suffix, 
        current_date
    )
    
    print(f"\nStarting export process for {region_text}...")
    print("This may take some time depending on the number of regions and resources...")
    
    print(f"Processing {len(regions)} regions: {', '.join(regions)}")
    
    # Import pandas for DataFrame handling (after dependency check)
    import pandas as pd
    
    # Dictionary to hold all DataFrames for export
    data_frames = {}
    
    # STEP 1: Collect VPC and Subnet information (if selected)
    if export_vpc_subnet:
        all_subnet_data = collect_vpc_subnet_data(regions)
        if all_subnet_data:
            data_frames['VPCs and Subnets'] = pd.DataFrame(all_subnet_data)
    
    # STEP 2: Collect NAT Gateway information (if selected)
    if export_nat_gateways:
        all_nat_gateway_data = collect_nat_gateway_data(regions)
        if all_nat_gateway_data:
            data_frames['NAT Gateways'] = pd.DataFrame(all_nat_gateway_data)
    
    # STEP 3: Collect VPC Peering information (if selected)
    if export_vpc_peering:
        all_vpc_peering_data = collect_vpc_peering_data(regions)
        if all_vpc_peering_data:
            data_frames['VPC Peering Connections'] = pd.DataFrame(all_vpc_peering_data)
    
    # STEP 4: Collect Elastic IP information (if selected)
    if export_elastic_ip:
        all_elastic_ip_data = collect_elastic_ip_data(regions)
        if all_elastic_ip_data:
            data_frames['Elastic IPs'] = pd.DataFrame(all_elastic_ip_data)
    
    # STEP 5: Save the Excel file using utils module
    if not data_frames:
        print("No data was collected. Nothing to export.")
        return
    
    # Use utils module to create the output directory if it doesn't exist
    output_path = utils.get_output_filepath(final_excel_file)
    
    try:
        # Create Excel writer
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Add each DataFrame as a separate worksheet
            for sheet_name, df in data_frames.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"Added {sheet_name} sheet with {len(df)} records")
        
        print(f"\nExport completed successfully! Data saved to {output_path}")
    except Exception as e:
        print(f"Error creating Excel file: {str(e)}")
        print("Export process completed with errors.")

def main():
    """Main function to execute the script."""
    try:
        # Print title and get account information
        account_id, account_name = print_title()
        
        # Check and install dependencies
        check_and_install_dependencies()
        
        # Export VPC, subnet, NAT Gateway, and VPC Peering information
        export_vpc_subnet_natgw_peering_info(account_id, account_name)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
