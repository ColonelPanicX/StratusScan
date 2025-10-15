#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS RDS Instance Export Script
Version: v2.0.0
Date: AUG-19-2025

Description:
This script exports a list of all RDS instances across available AWS
regions into a spreadsheet. The export includes DB Identifier, DB Cluster
Identifier, Role, Engine, Engine Version, RDS Extended Support, Region, Size,
Storage Type, Storage, Provisioned IOPS, Port, Endpoint, Master Username, VPC
(Name and ID), Subnet IDs, Security Groups (Name and ID), DB Subnet Group Name,
DB Certificate Expiry, Created Time, and Encryption information.
"""

import os
import sys
import datetime
import json
import boto3
import time
import botocore.exceptions
import csv
import re
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
    """
    Print the title banner for the script.
    
    Returns:
        tuple: (account_id, account_name) - AWS account ID and mapped account name
    """
    print("====================================================================")
    print("                   AWS RESOURCE SCANNER                            ")
    print("====================================================================")
    print("            AWS RDS INSTANCE EXPORT SCRIPT v2.1.0        ")
    print("====================================================================")
    
    # Get the current AWS account ID using STS (Security Token Service)
    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        
        # Validate AWS environment
        caller_arn = sts_client.get_caller_identity()['Arn']
        account_name = utils.get_account_name(account_id, default="UNKNOWN-ACCOUNT")
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
        print(f"Environment: AWS Commercial")
    except Exception as e:
        utils.log_error("Unable to determine account information", e)
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    print("====================================================================")
    return account_id, account_name

def check_and_install_dependencies():
    """
    Check for required dependencies and prompt to install if missing.
    This function ensures pandas and openpyxl are available for Excel export functionality.
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    # Check for each required package by attempting to import
    for package in required_packages:
        try:
            __import__(package)
            utils.log_info(f"[OK] {package} is already installed.")
        except ImportError:
            missing_packages.append(package)
    
    # If there are missing packages, prompt user to install them
    if missing_packages:
        utils.log_warning("Missing required dependencies:")
        for package in missing_packages:
            print(f"- {package}")
        
        while True:
            response = input("\nDo you want to install the missing dependencies? (y/n): ").strip().lower()
            if response == 'y':
                utils.log_info("Installing missing dependencies...")
                for package in missing_packages:
                    utils.log_info(f"Installing {package}...")
                    os.system(f"pip install {package}")
                
                # Verify installations by attempting to import again
                all_installed = True
                for package in missing_packages:
                    try:
                        __import__(package)
                        utils.log_success(f"{package} installed successfully.")
                    except ImportError:
                        utils.log_error(f"Failed to install {package}.")
                        all_installed = False
                
                if not all_installed:
                    utils.log_error("Some dependencies could not be installed. Please install them manually:")
                    for package in missing_packages:
                        print(f"pip install {package}")
                    sys.exit(1)
                break
            elif response == 'n':
                utils.log_error("Cannot proceed without required dependencies.")
                utils.log_info("Please install the following packages manually and try again:")
                for package in missing_packages:
                    print(f"pip install {package}")
                sys.exit(1)
            else:
                print("Invalid input. Please enter 'y' for yes or 'n' for no.")
    
    # Import required packages now that they're confirmed to be installed
    global pd
    import pandas as pd

def get_aws_regions():
    """
    Get a list of available AWS regions.
    
    Returns:
        list: A list of AWS region names
    """
    try:
        # Use utils function to get available AWS regions
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_aws_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        return utils.get_aws_regions()

def is_valid_aws_region(region_name):
    """
    Check if a region name is a valid AWS region.
    
    Args:
        region_name (str): AWS region name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return utils.validate_aws_region(region_name)

def get_security_group_info(rds_client, sg_ids):
    """
    Get security group names and IDs from a list of security group IDs.
    
    Args:
        rds_client: The boto3 RDS client (used to determine region)
        sg_ids (list): A list of security group IDs
        
    Returns:
        str: Formatted list of security group names and IDs in format "name (id), name (id), ..."
    """
    if not sg_ids:
        return ""
    
    try:
        # Create EC2 client in the same region as the RDS client
        region = rds_client.meta.region_name
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get security group information using EC2 describe_security_groups API
        response = ec2_client.describe_security_groups(GroupIds=sg_ids)
        # Format as "name (id), name (id), ..."
        sg_info = [f"{sg['GroupName']} ({sg['GroupId']})" for sg in response['SecurityGroups']]
        return ", ".join(sg_info)
    except Exception as e:
        # Return just the IDs if we can't get the names
        utils.log_warning(f"Could not get security group names for {sg_ids}: {e}")
        return ", ".join(sg_ids)

def get_vpc_info(rds_client, vpc_id):
    """
    Get VPC name and ID information from a VPC ID.
    
    Args:
        rds_client: The boto3 RDS client (used to determine region)
        vpc_id (str): The VPC ID
        
    Returns:
        str: Formatted VPC name and ID in format "name (id)" or just ID if name not found
    """
    if not vpc_id:
        return "N/A"
    
    try:
        # Create EC2 client in the same region as the RDS client
        region = rds_client.meta.region_name
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get VPC information using EC2 describe_vpcs API
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        if response['Vpcs']:
            vpc = response['Vpcs'][0]
            vpc_name = "Unnamed"
            # Check for Name tag in VPC tags
            for tag in vpc.get('Tags', []):
                if tag['Key'] == 'Name':
                    vpc_name = tag['Value']
                    break
            return f"{vpc_name} ({vpc_id})"
        return vpc_id
    except Exception as e:
        # Return just the ID if we can't get the VPC details
        utils.log_warning(f"Could not get VPC info for {vpc_id}: {e}")
        return vpc_id

def get_subnet_ids(subnet_group):
    """
    Extract subnet IDs from a DB subnet group.

    Args:
        subnet_group (dict): The DB subnet group information from RDS API

    Returns:
        str: Comma-separated list of subnet IDs
    """
    if not subnet_group or 'Subnets' not in subnet_group:
        return "N/A"

    try:
        # Extract subnet identifiers from the subnet group
        subnet_ids = [subnet['SubnetIdentifier'] for subnet in subnet_group['Subnets']]
        return ", ".join(subnet_ids)
    except Exception:
        return "N/A"

def load_rds_pricing_data():
    """
    Load RDS pricing data from the reference CSV file

    Returns:
        dict: Dictionary mapping instance types to pricing data for different engines
    """
    pricing_data = {}
    try:
        script_dir = Path(__file__).parent.absolute()
        pricing_file = script_dir.parent / 'reference' / 'rds-pricing.csv'

        if not pricing_file.exists():
            utils.log_warning(f"RDS pricing file not found at {pricing_file}")
            return pricing_data

        with open(pricing_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                instance_type = row.get('API Name', '').strip()
                if instance_type:
                    pricing_data[instance_type] = row

        utils.log_info(f"Loaded RDS pricing data for {len(pricing_data)} instance types")
        return pricing_data

    except Exception as e:
        utils.log_warning(f"Error loading RDS pricing data: {e}")
        return pricing_data

def load_storage_pricing_data():
    """
    Load EBS volume pricing data from the reference CSV file

    Returns:
        dict: Dictionary mapping volume types to cost per GB/month
    """
    storage_pricing = {}
    try:
        script_dir = Path(__file__).parent.absolute()
        pricing_file = script_dir.parent / 'reference' / 'ebsvol-pricing.csv'

        if not pricing_file.exists():
            utils.log_warning(f"Storage pricing file not found at {pricing_file}")
            return storage_pricing

        with open(pricing_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                volume_type = row.get('Type', '').strip()
                price_str = row.get(' Cost per GB/month ', '').strip()

                if volume_type and price_str:
                    price = parse_price(price_str)
                    if price is not None:
                        storage_pricing[volume_type] = price

        utils.log_info(f"Loaded storage pricing data for {len(storage_pricing)} volume types")
        return storage_pricing

    except Exception as e:
        utils.log_warning(f"Error loading storage pricing data: {e}")
        return storage_pricing

def parse_price(price_str):
    """
    Parse price string and return float value

    Args:
        price_str (str): Price string like "$157.826" or "unavailable"

    Returns:
        float or None: Parsed price or None if unavailable
    """
    if not price_str or price_str.lower() in ['unavailable', 'n/a', '']:
        return None

    # Remove currency symbols, commas, and spaces
    cleaned = re.sub(r'[$,\s]', '', price_str)

    try:
        return float(cleaned)
    except ValueError:
        return None

def calculate_rds_monthly_cost(instance_type, engine, pricing_data):
    """
    Calculate monthly cost for an RDS instance based on instance type and engine

    Args:
        instance_type (str): RDS instance type (e.g., 'db.m5.large')
        engine (str): Database engine (e.g., 'postgres', 'mysql', 'sqlserver-se')
        pricing_data (dict): RDS pricing data dictionary

    Returns:
        float or str: Monthly cost or 'N/A'
    """
    if instance_type not in pricing_data:
        return 'N/A'

    instance_pricing = pricing_data[instance_type]

    # Map engine to pricing column
    engine_lower = engine.lower()
    pricing_column = None

    if 'postgres' in engine_lower and 'aurora' not in engine_lower:
        pricing_column = 'PostgreSQL (Monthly)'
    elif 'mysql' in engine_lower and 'aurora' not in engine_lower:
        pricing_column = 'MySQL On Demand Cost (Monthly)'
    elif 'mariadb' in engine_lower:
        pricing_column = 'MariaDB On Demand Cost (Monthly)'
    elif 'aurora-postgresql' in engine_lower or 'aurora-mysql' in engine_lower:
        pricing_column = 'Aurora Postgres & MySQL On Demand Cost (Monthly)'
    elif 'sqlserver-ex' in engine_lower:
        pricing_column = 'SQL Server Expresss On Demand Cost (Monthly)'
    elif 'sqlserver-web' in engine_lower:
        pricing_column = 'SQL Server Web On Demand Cost (Monthly)'
    elif 'sqlserver-se' in engine_lower:
        pricing_column = 'SQL Server Standard On Demand Cost (Monthly)'
    elif 'sqlserver-ee' in engine_lower:
        pricing_column = 'SQL Server Enterprise On Demand Cost (Monthly)'
    elif 'oracle' in engine_lower:
        pricing_column = 'Oracle Enterprise On Demand Cost (Monthly)'
    else:
        return 'N/A'

    price_str = instance_pricing.get(pricing_column, '').strip()
    price = parse_price(price_str)

    return price if price is not None else 'N/A'

def calculate_rds_storage_cost(storage_size, storage_type, storage_pricing):
    """
    Calculate monthly storage cost for an RDS instance

    Args:
        storage_size (int): Storage size in GB
        storage_type (str): Storage type (gp2, gp3, io1, etc.)
        storage_pricing (dict): Storage pricing data

    Returns:
        float or str: Monthly storage cost or 'N/A'
    """
    try:
        if storage_size == 'N/A' or storage_type == 'N/A':
            return 'N/A'

        # Get price per GB for the storage type
        price_per_gb = storage_pricing.get(storage_type, storage_pricing.get('gp3', 0.08))

        if price_per_gb is None:
            return 'N/A'

        total_cost = float(storage_size) * price_per_gb
        return round(total_cost, 2)

    except Exception as e:
        utils.log_warning(f"Error calculating storage cost: {e}")
        return 'N/A'

def get_rds_instances(region):
    """
    Get all RDS instances in a specific AWS region with detailed information.
    
    Args:
        region (str): AWS region name
        
    Returns:
        list: List of dictionaries containing RDS instance information
    """
    # Validate region is AWS
    if not utils.validate_aws_region(region):
        utils.log_error(f"Invalid AWS region: {region}")
        return []

    rds_instances = []

    # Load pricing data
    pricing_data = load_rds_pricing_data()
    storage_pricing = load_storage_pricing_data()

    try:
        # Create RDS client for the specified AWS region
        rds_client = boto3.client('rds', region_name=region)
        
        # Get all DB instances using pagination to handle large numbers of instances
        paginator = rds_client.get_paginator('describe_db_instances')
        page_iterator = paginator.paginate()

        # Count total instances first for progress tracking
        total_instances = 0
        for page in paginator.paginate():
            total_instances += len(page['DBInstances'])

        if total_instances > 0:
            utils.log_info(f"Found {total_instances} RDS instances in {region} to process")

        # Reset paginator for actual processing
        paginator = rds_client.get_paginator('describe_db_instances')
        page_iterator = paginator.paginate()

        # Process each page of results
        processed = 0
        for page in page_iterator:
            for instance in page['DBInstances']:
                processed += 1
                instance_id = instance.get('DBInstanceIdentifier', 'Unknown')
                progress = (processed / total_instances) * 100 if total_instances > 0 else 0

                utils.log_info(f"[{progress:.1f}%] Processing RDS instance {processed}/{total_instances}: {instance_id}")
                # Extract security group IDs from VPC security groups
                sg_ids = [sg['VpcSecurityGroupId'] for sg in instance.get('VpcSecurityGroups', [])]
                sg_info = get_security_group_info(rds_client, sg_ids)
                
                # Get VPC information from DB subnet group
                vpc_id = instance.get('DBSubnetGroup', {}).get('VpcId', 'N/A')
                vpc_info = get_vpc_info(rds_client, vpc_id) if vpc_id != 'N/A' else 'N/A'
                
                # Get subnet IDs from DB subnet group
                subnet_ids = get_subnet_ids(instance.get('DBSubnetGroup', {}))
                
                # Get port information from endpoint
                port = instance.get('Endpoint', {}).get('Port', 'N/A') if 'Endpoint' in instance else 'N/A'
                
                # Get endpoint address - RDS connection endpoint
                endpoint_address = instance.get('Endpoint', {}).get('Address', 'N/A') if 'Endpoint' in instance else 'N/A'
                
                # Get master username - the primary database user
                master_username = instance.get('MasterUsername', 'N/A')
                
                # Determine if instance is part of a cluster and its role
                db_cluster_id = instance.get('DBClusterIdentifier', 'N/A')
                role = 'Standalone'
                if db_cluster_id != 'N/A':
                    try:
                        # Get cluster info to determine if this instance is primary or replica
                        cluster_info = rds_client.describe_db_clusters(
                            DBClusterIdentifier=db_cluster_id
                        )
                        if cluster_info and 'DBClusters' in cluster_info and cluster_info['DBClusters']:
                            cluster = cluster_info['DBClusters'][0]
                            # Check if this instance is the primary (writer) in the cluster
                            if 'DBClusterMembers' in cluster:
                                for member in cluster['DBClusterMembers']:
                                    if member.get('DBInstanceIdentifier') == instance['DBInstanceIdentifier']:
                                        role = 'Primary' if member.get('IsClusterWriter', False) else 'Replica'
                    except Exception as e:
                        # If we can't determine cluster role, leave as default
                        utils.log_warning(f"Could not determine cluster role for {instance['DBInstanceIdentifier']}: {e}")
                
                # Check for RDS Extended Support status
                extended_support = 'No'
                try:
                    if 'StatusInfos' in instance:
                        for status_info in instance['StatusInfos']:
                            if status_info.get('Status') == 'extended-support':
                                extended_support = 'Yes'
                except Exception:
                    pass
                
                # Format certificate expiry date
                cert_expiry = 'N/A'
                try:
                    if 'CertificateDetails' in instance and 'ValidTill' in instance['CertificateDetails']:
                        valid_till = instance['CertificateDetails']['ValidTill']
                        if isinstance(valid_till, datetime.datetime):
                            cert_expiry = valid_till.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
                
                # Format creation time
                created_time = 'N/A'
                try:
                    if 'InstanceCreateTime' in instance:
                        create_time = instance['InstanceCreateTime']
                        if isinstance(create_time, datetime.datetime):
                            created_time = create_time.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
                
                # Create comprehensive instance data dictionary
                # Calculate monthly cost
                monthly_cost = calculate_rds_monthly_cost(
                    instance['DBInstanceClass'],
                    instance['Engine'],
                    pricing_data
                )

                # Calculate storage cost
                storage_cost = calculate_rds_storage_cost(
                    instance['AllocatedStorage'],
                    instance['StorageType'],
                    storage_pricing
                )

                # Calculate total monthly cost
                total_monthly_cost = 'N/A'
                if monthly_cost != 'N/A' and storage_cost != 'N/A':
                    total_monthly_cost = round(float(monthly_cost) + float(storage_cost), 2)
                elif monthly_cost != 'N/A':
                    total_monthly_cost = float(monthly_cost)
                elif storage_cost != 'N/A':
                    total_monthly_cost = float(storage_cost)

                instance_data = {
                    'DB Identifier': instance['DBInstanceIdentifier'],
                    'DB Cluster Identifier': db_cluster_id,
                    'Role': role,
                    'Engine': instance['Engine'],
                    'Engine Version': instance['EngineVersion'],
                    'RDS Extended Support': extended_support,
                    'Region': region,
                    'Size': instance['DBInstanceClass'],
                    'Monthly Cost (On-Demand)': monthly_cost,
                    'Monthly Storage Cost': storage_cost,
                    'Total Monthly Cost': total_monthly_cost,
                    'Storage Type': instance['StorageType'],
                    'Storage (GB)': instance['AllocatedStorage'],
                    'Provisioned IOPS': instance.get('Iops', 'N/A'),
                    'Port': port,
                    'Endpoint': endpoint_address,  # RDS connection endpoint
                    'Master Username': master_username,  # Primary database user
                    'VPC': vpc_info,
                    'Subnet IDs': subnet_ids,
                    'Security Groups': sg_info,
                    'DB Subnet Group Name': instance.get('DBSubnetGroup', {}).get('DBSubnetGroupName', 'N/A'),
                    'DB Certificate Expiry': cert_expiry,
                    'Created Time': created_time,
                    'Encryption': 'Yes' if instance.get('StorageEncrypted', False) else 'No',
                    'Owner ID': utils.get_account_name_formatted(instance.get('OwnerId', 'N/A'))
                }
                
                rds_instances.append(instance_data)

                # Small delay to avoid API throttling
                if processed < total_instances:  # Don't delay after the last instance
                    time.sleep(0.1)
        
        return rds_instances
    except botocore.exceptions.ClientError as e:
        # Handle specific AWS client errors
        if e.response['Error']['Code'] == 'AccessDenied':
            utils.log_warning(f"Access denied in AWS region {region}. Skipping...")
        elif e.response['Error']['Code'] == 'AuthFailure':
            utils.log_warning(f"Authentication failure in AWS region {region}. Skipping...")
        else:
            utils.log_error(f"Error in AWS region {region}", e)
        return []
    except Exception as e:
        utils.log_error(f"Error accessing AWS region {region}", e)
        return []

def export_to_excel(data, account_name, region_filter=None):
    """
    Export RDS instance data to an Excel file using pandas and openpyxl.
    
    Args:
        data (list): List of dictionaries containing RDS instance information
        account_name (str): Name of the AWS account for filename
        region_filter (str, optional): Region filter to include in filename
        
    Returns:
        str: Path to the exported file, or None if export failed
    """
    if not data:
        utils.log_warning("No RDS instances found to export.")
        return None
    
    try:
        # Import pandas (should be installed by now)
        import pandas as pd
        
        # Process data to remove timezone information from datetime objects
        processed_data = []
        for item in data:
            processed_item = {}
            for key, value in item.items():
                if isinstance(value, datetime.datetime) and value.tzinfo is not None:
                    processed_item[key] = value.replace(tzinfo=None)
                else:
                    processed_item[key] = value
            processed_data.append(processed_item)
        
        # Convert processed data to pandas DataFrame
        df = pd.DataFrame(processed_data)
        
        # Define output file name with date and optional region filter
        today = datetime.datetime.now().strftime("%m.%d.%Y")
        region_suffix = f"{region_filter}" if region_filter else ""
        
        # Use the utility function for consistent AWS file naming
        filename = utils.create_export_filename(
            account_name, 
            "rds-instances", 
            region_suffix, 
            today
        )
        
        # Save using utils function
        saved_file = utils.save_dataframe_to_excel(df, filename, sheet_name='RDS Instances')
        
        if saved_file:
            utils.log_success("AWS RDS data exported successfully!")
            utils.log_info(f"File location: {saved_file}")
            return saved_file
        else:
            utils.log_error("Failed to save using utils.save_dataframe_to_excel()")
            return None
            
    except Exception as e:
        utils.log_error("Error exporting data", e)
        
        # Fallback to CSV if Excel export fails
        try:
            import pandas as pd
            csv_filename = filename.replace('.xlsx', '.csv')
            csv_file = utils.get_output_filepath(csv_filename)
            pd.DataFrame(data).to_csv(csv_file, index=False)
            utils.log_info(f"Exported to CSV instead: {csv_file}")
            return str(csv_file)
        except Exception as csv_error:
            utils.log_error("CSV export also failed", csv_error)
            return None

def main():
    """
    Main function to coordinate the AWS RDS instance export process.
    This function orchestrates the entire workflow from user input to final export.
    """
    # Print script title and get account information
    account_id, account_name = print_title()
    
    # Check and install dependencies before proceeding
    check_and_install_dependencies()
    
    if account_name == "UNKNOWN-ACCOUNT":
        proceed = utils.prompt_for_confirmation("Unable to determine account name. Proceed anyway?", default=False)
        if not proceed:
            utils.log_info("Exiting script...")
            sys.exit(0)
    
    # Get user input for AWS region selection
    print("\nAWS Region Selection:")
    print("Would you like the information for all AWS regions or a specific region?")
    print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
    region_choice = input("If all, write \"all\", or specify a AWS region name: ").strip().lower()
    
    # Get all available AWS regions for validation
    all_aws_regions = get_aws_regions()
    
    # Determine which regions to scan based on user input
    if region_choice == "all":
        regions_to_scan = all_aws_regions
        region_filter = None
        utils.log_info(f"Scanning all available AWS regions: {', '.join(regions_to_scan)}")
    else:
        # Validate the region name against available AWS regions
        if not is_valid_aws_region(region_choice):
            utils.log_warning(f"'{region_choice}' is not a valid AWS region.")
            utils.log_info("Valid AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
            utils.log_info("Defaulting to scanning all AWS regions.")
            regions_to_scan = all_aws_regions
            region_filter = None
        else:
            regions_to_scan = [region_choice]
            region_filter = region_choice
            utils.log_info(f"Scanning only the {region_choice} AWS region.")
    
    # Initialize data collection list
    all_rds_instances = []
    
    utils.log_info(f"Collecting RDS instance data across {len(regions_to_scan)} AWS region(s)...")
    
    # Process each region and collect RDS instance data
    for region in regions_to_scan:
        utils.log_info(f"Searching for RDS instances in AWS region: {region}")
        
        # Get RDS instances in the current region
        region_instances = get_rds_instances(region)
        
        # Add region instances to the total collection
        all_rds_instances.extend(region_instances)
        
        # Display count for this region for user feedback
        utils.log_info(f"Found {len(region_instances)} RDS instances in {region}")
    
    # Export results to Excel file
    utils.log_success(f"Found {len(all_rds_instances)} RDS instances in total across all AWS regions.")
    
    if all_rds_instances:
        output_file = export_to_excel(all_rds_instances, account_name, region_filter)
        if output_file:
            utils.log_info(f"Export contains data from {len(regions_to_scan)} AWS region(s)")
            utils.log_info(f"Total RDS instances exported: {len(all_rds_instances)}")
            print("\nScript execution completed.")
        else:
            utils.log_error("Failed to export data. Please check the logs.")
            sys.exit(1)
    else:
        utils.log_warning("No RDS instances found in any AWS region. No file exported.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        utils.log_error("An unexpected error occurred", e)
        sys.exit(1)