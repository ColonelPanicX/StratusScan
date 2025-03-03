#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS RDS Instance Export Script
Version: v1.1.1
Date: FEB-28-2025

Description: 
This script exports a list of all RDS instances across all AWS 
regions into a spreadsheet. The export includes DB Identifier, DB Cluster 
Identifier, Role, Engine, Engine Version, RDS Extended Support, Region, Size, 
Storage Type, Storage, Provisioned IOPS, Port, VPC (Name and ID), Subnet IDs, 
Security Groups (Name and ID), DB Subnet Group Name, DB Certificate Expiry, 
Created Time, and Encryption information.
"""

import os
import sys
import datetime
import json
import boto3
import time
import botocore.exceptions
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
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS RDS INSTANCE EXPORT SCRIPT v1.1.1")
    print("====================================================================")
    
    # Get the current AWS account ID
    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        account_name = utils.get_account_name(account_id, default="UNKNOWN")
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print("Unable to determine account information.")
        print(f"Error: {e}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN"
    
    print("====================================================================")
    return account_id, account_name

def check_and_install_dependencies():
    """
    Check for required dependencies and prompt to install if missing.
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    # Check for each required package
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is already installed.")
        except ImportError:
            missing_packages.append(package)
    
    # If there are missing packages, prompt to install them
    if missing_packages:
        print("\nMissing required dependencies:")
        for package in missing_packages:
            print(f"- {package}")
        
        while True:
            response = input("\nDo you want to install the missing dependencies? (y/n): ").strip().lower()
            if response == 'y':
                print("\nInstalling missing dependencies...")
                for package in missing_packages:
                    print(f"Installing {package}...")
                    os.system(f"pip install {package}")
                
                # Verify installations
                all_installed = True
                for package in missing_packages:
                    try:
                        __import__(package)
                        print(f"✓ {package} installed successfully.")
                    except ImportError:
                        print(f"✗ Failed to install {package}.")
                        all_installed = False
                
                if not all_installed:
                    print("\nSome dependencies could not be installed. Please install them manually:")
                    for package in missing_packages:
                        print(f"pip install {package}")
                    sys.exit(1)
                break
            elif response == 'n':
                print("\nCannot proceed without required dependencies.")
                print("Please install the following packages manually and try again:")
                for package in missing_packages:
                    print(f"pip install {package}")
                sys.exit(1)
            else:
                print("Invalid input. Please enter 'y' for yes or 'n' for no.")
    
    # Import required packages now that they're installed
    global pd
    import pandas as pd

def get_all_regions():
    """
    Get a list of all available AWS regions.
    
    Returns:
        list: A list of region names.
    """
    try:
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        regions = [region['RegionName'] for region in response['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        # Return a default list of common regions
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-west-3',
            'eu-central-1', 'eu-north-1', 'ap-northeast-1',
            'ap-northeast-2', 'ap-northeast-3', 'ap-southeast-1',
            'ap-southeast-2', 'ap-south-1', 'sa-east-1'
        ]

def get_security_group_info(rds_client, sg_ids):
    """
    Get security group names and IDs.
    
    Args:
        rds_client: The boto3 RDS client
        sg_ids (list): A list of security group IDs
        
    Returns:
        str: Formatted list of security group names and IDs
    """
    if not sg_ids:
        return ""
    
    try:
        # Create EC2 client in the same region as the RDS client
        region = rds_client.meta.region_name
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get security group information
        response = ec2_client.describe_security_groups(GroupIds=sg_ids)
        # Format as "name (id), name (id), ..."
        sg_info = [f"{sg['GroupName']} ({sg['GroupId']})" for sg in response['SecurityGroups']]
        return ", ".join(sg_info)
    except Exception as e:
        # Return IDs if we can't get names
        return ", ".join(sg_ids)

def get_vpc_info(rds_client, vpc_id):
    """
    Get VPC name and ID information.
    
    Args:
        rds_client: The boto3 RDS client
        vpc_id (str): The VPC ID
        
    Returns:
        str: Formatted VPC name and ID
    """
    if not vpc_id:
        return "N/A"
    
    try:
        # Create EC2 client in the same region as the RDS client
        region = rds_client.meta.region_name
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get VPC information
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        if response['Vpcs']:
            vpc = response['Vpcs'][0]
            vpc_name = "Unnamed"
            # Check for Name tag
            for tag in vpc.get('Tags', []):
                if tag['Key'] == 'Name':
                    vpc_name = tag['Value']
                    break
            return f"{vpc_name} ({vpc_id})"
        return vpc_id
    except Exception as e:
        # Return ID if we can't get name
        return vpc_id

def get_subnet_ids(subnet_group):
    """
    Extract subnet IDs from a DB subnet group.
    
    Args:
        subnet_group (dict): The DB subnet group information
        
    Returns:
        str: Comma-separated list of subnet IDs
    """
    if not subnet_group or 'Subnets' not in subnet_group:
        return "N/A"
    
    try:
        subnet_ids = [subnet['SubnetIdentifier'] for subnet in subnet_group['Subnets']]
        return ", ".join(subnet_ids)
    except Exception:
        return "N/A"

def get_rds_instances(region):
    """
    Get all RDS instances in a specific region.
    
    Args:
        region (str): AWS region name
        
    Returns:
        list: List of dictionaries containing RDS instance information
    """
    rds_instances = []
    try:
        # Create RDS client for the specified region
        rds_client = boto3.client('rds', region_name=region)
        
        # Get all DB instances
        paginator = rds_client.get_paginator('describe_db_instances')
        page_iterator = paginator.paginate()
        
        # Process each page of results
        for page in page_iterator:
            for instance in page['DBInstances']:
                # Extract security group IDs
                sg_ids = [sg['VpcSecurityGroupId'] for sg in instance.get('VpcSecurityGroups', [])]
                sg_info = get_security_group_info(rds_client, sg_ids)
                
                # Get VPC information
                vpc_id = instance.get('DBSubnetGroup', {}).get('VpcId', 'N/A')
                vpc_info = get_vpc_info(rds_client, vpc_id) if vpc_id != 'N/A' else 'N/A'
                
                # Get subnet IDs
                subnet_ids = get_subnet_ids(instance.get('DBSubnetGroup', {}))
                
                # Get port information
                port = instance.get('Endpoint', {}).get('Port', 'N/A') if 'Endpoint' in instance else 'N/A'
                
                # Determine if instance is part of a cluster and its role
                db_cluster_id = instance.get('DBClusterIdentifier', 'N/A')
                role = 'Standalone'
                if db_cluster_id != 'N/A':
                    try:
                        # Get cluster info to determine role
                        cluster_info = rds_client.describe_db_clusters(
                            DBClusterIdentifier=db_cluster_id
                        )
                        if cluster_info and 'DBClusters' in cluster_info and cluster_info['DBClusters']:
                            cluster = cluster_info['DBClusters'][0]
                            # Check if this instance is the primary (writer)
                            if 'DBClusterMembers' in cluster:
                                for member in cluster['DBClusterMembers']:
                                    if member.get('DBInstanceIdentifier') == instance['DBInstanceIdentifier']:
                                        role = 'Primary' if member.get('IsClusterWriter', False) else 'Replica'
                    except Exception:
                        # If we can't determine, leave as is
                        pass
                
                # Check for RDS Extended Support
                extended_support = 'No'
                try:
                    if 'StatusInfos' in instance:
                        for status_info in instance['StatusInfos']:
                            if status_info.get('Status') == 'extended-support':
                                extended_support = 'Yes'
                except Exception:
                    pass
                
                # Create instance data dictionary
                instance_data = {
                    'DB Identifier': instance['DBInstanceIdentifier'],
                    'DB Cluster Identifier': db_cluster_id,
                    'Role': role,
                    'Engine': instance['Engine'],
                    'Engine Version': instance['EngineVersion'],
                    'RDS Extended Support': extended_support,
                    'Region': region,
                    'Size': instance['DBInstanceClass'],
                    'Storage Type': instance['StorageType'],
                    'Storage (GB)': instance['AllocatedStorage'],
                    'Provisioned IOPS': instance.get('Iops', 'N/A'),
                    'Port': port,
                    'VPC': vpc_info,
                    'Subnet IDs': subnet_ids,
                    'Security Groups': sg_info,
                    'DB Subnet Group Name': instance.get('DBSubnetGroup', {}).get('DBSubnetGroupName', 'N/A'),
                    'DB Certificate Expiry': instance.get('CertificateDetails', {}).get('ValidTill', 'N/A').replace(tzinfo=None) if isinstance(instance.get('CertificateDetails', {}).get('ValidTill', 'N/A'), datetime.datetime) else 'N/A',
                    'Created Time': instance['InstanceCreateTime'].replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S') if 'InstanceCreateTime' in instance else 'N/A',
                    'Encryption': 'Yes' if instance.get('StorageEncrypted', False) else 'No'
                }
                
                rds_instances.append(instance_data)
        
        return rds_instances
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            print(f"Access denied in region {region}. Skipping...")
        elif e.response['Error']['Code'] == 'AuthFailure':
            print(f"Authentication failure in region {region}. Skipping...")
        else:
            print(f"Error in region {region}: {e}")
        return []
    except Exception as e:
        print(f"Error accessing region {region}: {e}")
        return []

def export_to_excel(data, account_name):
    """
    Export RDS instance data to an Excel file.
    
    Args:
        data (list): List of dictionaries containing RDS instance information
        account_name (str): Name of the AWS account
        
    Returns:
        str: Path to the exported file
    """
    # Helper function to make datetime objects timezone unaware
    def remove_timezone(obj):
        if isinstance(obj, datetime.datetime) and obj.tzinfo is not None:
            return obj.replace(tzinfo=None)
        return obj
    if not data:
        print("No RDS instances found to export.")
        return None
    
    try:
        # Import pandas (should be installed by now)
        import pandas as pd
        
        # Process data to remove timezone information from all datetime objects
        processed_data = []
        for item in data:
            processed_item = {}
            for key, value in item.items():
                if isinstance(value, datetime.datetime) and value.tzinfo is not None:
                    processed_item[key] = value.replace(tzinfo=None)
                else:
                    processed_item[key] = value
            processed_data.append(processed_item)
        
        # Convert processed data to DataFrame
        df = pd.DataFrame(processed_data)
        
        # Define output file name with date
        today = datetime.datetime.now().strftime("%m.%d.%Y")
        
        # Create output directory if it doesn't exist
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Create full output path
        output_file = output_dir / f"{account_name}-rds-instances-export-{today}.xlsx"
        
        # Create Excel writer
        writer = pd.ExcelWriter(output_file, engine='openpyxl')
        
        # Write data to Excel
        df.to_excel(writer, sheet_name='RDS Instances', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['RDS Instances']
        for i, column in enumerate(df.columns):
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            # Set a maximum column width to avoid extremely wide columns
            column_width = min(column_width, 50)
            # openpyxl column indices are 1-based
            worksheet.column_dimensions[chr(65 + i if i < 26 else 64 + i//26 + 1)].width = column_width
        
        # Save the Excel file
        writer.close()
        
        print(f"\nExport completed successfully!")
        print(f"File saved as: {os.path.abspath(output_file)}")
        
        return output_file
    except Exception as e:
        print(f"Error exporting data: {e}")
        
        # Fallback to CSV if Excel export fails
        try:
            csv_file = output_dir / f"{account_name}-rds-instances-export-{datetime.datetime.now().strftime('%m.%d.%Y')}.csv"
            pd.DataFrame(data).to_csv(csv_file, index=False)
            print(f"Exported to CSV instead: {os.path.abspath(csv_file)}")
            return csv_file
        except Exception as csv_error:
            print(f"CSV export also failed: {csv_error}")
            return None

def main():
    """
    Main function to coordinate the RDS instance export process.
    """
    # Print script title and get account information
    account_id, account_name = print_title()
    
    # Check and install dependencies
    check_and_install_dependencies()
    
    # Get all available regions
    print("\nGetting list of AWS regions...")
    regions = get_all_regions()
    print(f"Found {len(regions)} regions.")
    
    # Initialize data collection
    all_rds_instances = []
    processed_regions = 0
    total_regions = len(regions)
    
    print("\nCollecting RDS instance data across all regions...")
    
    # Process each region
    for region in regions:
        processed_regions += 1
        progress = (processed_regions / total_regions) * 100
        sys.stdout.write(f"\rProgress: {progress:.1f}% - Processing region: {region} ({processed_regions}/{total_regions})")
        sys.stdout.flush()
        
        # Get RDS instances in the region
        region_instances = get_rds_instances(region)
        all_rds_instances.extend(region_instances)
    
    sys.stdout.write("\n")
    
    # Export results
    print(f"\nFound {len(all_rds_instances)} RDS instances across {len(regions)} regions.")
    
    if all_rds_instances:
        output_file = export_to_excel(all_rds_instances, account_name)
        if output_file:
            print("\nExport complete! You can find the exported file in the current directory.")
            print(f"File path: {os.path.abspath(output_file)}")
    else:
        print("No RDS instances found. No file exported.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")
        sys.exit(1)
