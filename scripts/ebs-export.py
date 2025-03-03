#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EBS Volume Data Export
Version: v1.0.1
Date: FEB-28-2025

Description: 
This script collects EBS volume information across all AWS regions in an account
and exports the data to a CSV file. The data includes volume ID, name, size,
state, and instance ID (if attached).

"""

import boto3
import os
import datetime
import csv
import sys
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

def check_and_install_dependencies():
    """
    Check if required dependencies are installed and offer to install them if they are not.
    """
    try:
        # Try to import pandas to check if it's installed
        import pandas
        print("Pandas is already installed.")
    except ImportError:
        # If pandas is not installed, ask the user if they want to install it
        response = input("Pandas is not installed. Would you like to install it? (y/n): ")
        if response.lower() == 'y':
            # Install pandas using pip
            print("Installing pandas...")
            os.system(f"{sys.executable} -m pip install pandas")
            print("Pandas installed successfully.")
        else:
            print("Pandas installation skipped. Note that this script requires pandas to function properly.")
            sys.exit(1)

def get_current_account_id():
    """
    Get the AWS account ID of the current session.
    
    Returns:
        str: The AWS account ID
    """
    # Create a boto3 STS client to get account information
    sts_client = boto3.client('sts')
    # Get the account ID from the STS GetCallerIdentity API call
    account_id = sts_client.get_caller_identity()["Account"]
    return account_id

def get_all_regions():
    """
    Get a list of all available AWS regions.
    
    Returns:
        list: List of region names
    """
    # Create a boto3 EC2 client to get region information
    ec2_client = boto3.client('ec2')
    # Describe all regions using the EC2 DescribeRegions API call
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
    return regions

def get_ebs_volumes(region):
    """
    Get all EBS volumes in a specific region.
    
    Args:
        region (str): AWS region name
        
    Returns:
        list: List of volume dictionaries with relevant information
    """
    # Create a boto3 EC2 client for the specified region
    ec2_client = boto3.client('ec2', region_name=region)
    
    # Initialize an empty list to store volume information
    volumes_data = []
    
    # Use pagination to handle large numbers of volumes
    paginator = ec2_client.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for volume in page['Volumes']:
            # Initialize variables for volume data
            volume_name = "N/A"
            instance_id = "Not attached"
            
            # Extract volume name from tags if available
            if 'Tags' in volume:
                for tag in volume['Tags']:
                    if tag['Key'] == 'Name':
                        volume_name = tag['Value']
                        break
            
            # Get instance ID if the volume is attached
            if volume['Attachments']:
                instance_id = volume['Attachments'][0]['InstanceId']
            
            # Add volume data to the list
            volumes_data.append({
                'Region': region,
                'VolumeId': volume['VolumeId'],
                'Name': volume_name,
                'Size (GB)': volume['Size'],
                'State': volume['State'],
                'AttachedTo': instance_id,
                'VolumeType': volume['VolumeType'],
                'Encrypted': volume['Encrypted'],
                'CreateTime': volume['CreateTime'].strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return volumes_data

def export_to_csv(account_name, volumes_data):
    """
    Export volumes data to a CSV file.
    
    Args:
        account_name (str): Name of the AWS account
        volumes_data (list): List of volume dictionaries
        
    Returns:
        str: Path to the exported CSV file
    """
    # Get current date for filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create filename based on account name and current date
    filename = f"{account_name}-ebs-volumes-export-{current_date}.csv"
    
    # Define CSV headers
    headers = [
        'Region', 
        'VolumeId', 
        'Name', 
        'Size (GB)', 
        'State', 
        'AttachedTo', 
        'VolumeType', 
        'Encrypted', 
        'CreateTime'
    ]
    
    # Get output directory path
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Full path for the output file
    output_path = output_dir / filename
    
    # Write data to CSV file
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(volumes_data)
    
    # Return the path to the created file
    return os.path.abspath(output_path)

def create_excel_file(account_name, volumes_data):
    """
    Export volumes data to an Excel file using pandas.
    
    Args:
        account_name (str): Name of the AWS account
        volumes_data (list): List of volume dictionaries
        
    Returns:
        str: Path to the exported Excel file
    """
    # Import pandas here to avoid issues if it's not installed
    import pandas as pd
    
    # Get current date for filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create filename based on account name and current date
    filename = f"{account_name}-ebs-volumes-export-{current_date}.xlsx"
    
    # Get output directory path
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Full path for the output file
    output_path = output_dir / filename
    
    # Convert data to pandas DataFrame
    df = pd.DataFrame(volumes_data)
    
    # Write data to Excel file
    df.to_excel(output_path, index=False)
    
    # Return the path to the created file
    return os.path.abspath(output_path)

def print_title():
    """
    Print a formatted title for the script.
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS EBS VOLUME DATA EXPORT")
    print("====================================================================")
    
    account_id = get_current_account_id()
    account_name = utils.get_account_name(account_id, default=f"UNKNOWN-{account_id}")
    
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    return account_id, account_name

def main():
    """
    Main function to execute the script.
    """
    # Check and install required dependencies
    check_and_install_dependencies()
    
    # Print the script title and get account information
    account_id, account_name = print_title()
    
    # Get all available AWS regions
    print("Getting list of AWS regions...")
    regions = get_all_regions()
    print(f"Found {len(regions)} regions.")
    
    # Initialize an empty list to store volume data from all regions
    all_volumes = []
    
    # Iterate through each region and collect volume data
    for i, region in enumerate(regions):
        print(f"Collecting EBS volume data from {region} ({i+1}/{len(regions)})...")
        try:
            # Get EBS volumes for the current region
            region_volumes = get_ebs_volumes(region)
            all_volumes.extend(region_volumes)
            print(f"  Found {len(region_volumes)} volumes in {region}.")
        except Exception as e:
            # Handle exceptions for regions that might not be accessible
            print(f"  Error collecting data from {region}: {str(e)}")
    
    # Print summary of collected data
    print(f"Total EBS volumes found across all regions: {len(all_volumes)}")
    
    # Try to export to Excel first
    try:
        print("Exporting data to Excel format...")
        excel_path = create_excel_file(account_name, all_volumes)
        print(f"Data exported to Excel: {excel_path}")
    except Exception as e:
        print(f"Error exporting to Excel: {str(e)}")
        print("Falling back to CSV export...")
        # Fall back to CSV export if Excel export fails
        csv_path = export_to_csv(account_name, all_volumes)
        print(f"Data exported to CSV: {csv_path}")
    
    print("Script execution completed.")

if __name__ == "__main__":
    main()
