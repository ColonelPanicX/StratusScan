#!/usr/bin/env python3

""" 
===========================
= AWS RESOURCE SCANNER =
===========================

Title: S3 Bucket Inventory Export 
Version: v1.1.2
Date: FEB-28-2025 

Description: This script exports information about S3 buckets across all AWS 
regions including bucket name, region, creation date, and total object count.
Bucket sizes are retrieved using S3 Storage Lens where available.
The data is exported to a spreadsheet file with a standardized naming convention.

"""

import boto3
import pandas as pd
import sys
import os
import datetime
import argparse
import time
from botocore.exceptions import ClientError
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
    Prints a formatted title banner for the script to the console
    """
    # Get the current AWS account ID using STS
    sts_client = boto3.client('sts')
    try:
        # Get the current account ID
        account_id = sts_client.get_caller_identity()["Account"]
        # Get the account name from the utils module
        account_name = utils.get_account_name(account_id, default="UNKNOWN")
    except Exception as e:
        print(f"Error retrieving account information: {e}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN"
        
    # Print a formatted title banner
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("S3 BUCKET INVENTORY EXPORT SCRIPT")
    print("====================================================================")
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    
    return account_id, account_name

def check_dependencies():
    """
    Checks if required dependencies are installed and prompts the user to install if missing
    
    Returns:
        bool: True if all dependencies are installed or user chose to install, False otherwise
    """
    required_packages = ['pandas', 'boto3', 'openpyxl']
    missing_packages = []
    
    # Check for each required package
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    # If there are missing packages, prompt user to install
    if missing_packages:
        print(f"The following required packages are missing: {', '.join(missing_packages)}")
        install_choice = input("Do you want to install these packages? ('y' for yes, 'n' for no): ")
        
        if install_choice.lower() == 'y':
            # Attempt to install the missing packages
            import subprocess
            for package in missing_packages:
                try:
                    print(f"Installing {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to install {package}: {e}")
                    return False
            return True
        else:
            print("Script cannot continue without required dependencies.")
            return False
    
    return True

def get_all_regions():
    """
    Get a list of all available AWS regions
    
    Returns:
        list: List of region names
    """
    # Create an EC2 client to get the list of regions
    ec2_client = boto3.client('ec2', region_name='us-east-1')
    
    try:
        # Get all regions
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error retrieving AWS regions: {e}")
        # Return a default list of common regions if we can't get the complete list
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1'
        ]

def get_bucket_region(bucket_name):
    """
    Determine the region of a specific S3 bucket
    
    Args:
        bucket_name (str): Name of the S3 bucket
        
    Returns:
        str: AWS region name of the bucket
    """
    # Create an S3 client without specifying a region
    s3_client = boto3.client('s3')
    
    try:
        # Get the bucket's location
        response = s3_client.get_bucket_location(Bucket=bucket_name)
        location = response['LocationConstraint']
        
        # AWS returns None for us-east-1 (it's the default)
        if location is None:
            return 'us-east-1'
        return location
    except Exception as e:
        print(f"Error getting region for bucket {bucket_name}: {e}")
        return "unknown"

def get_bucket_object_count(bucket_name, region):
    """
    Get the total number of objects in a bucket
    
    Args:
        bucket_name (str): Name of the S3 bucket
        region (str): AWS region where the bucket is located
        
    Returns:
        int: Total number of objects in the bucket
    """
    # Create an S3 client in the bucket's region
    s3_client = boto3.client('s3', region_name=region)
    
    total_objects = 0
    
    try:
        # Use a paginator to handle buckets with many objects
        paginator = s3_client.get_paginator('list_objects_v2')
        
        # Paginate through all objects in the bucket
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                total_objects += len(page['Contents'])
                    
        return total_objects
    except Exception as e:
        print(f"Error counting objects for bucket {bucket_name}: {e}")
        return 0

def check_storage_lens_availability():
    """
    Check if S3 Storage Lens is configured and available
    
    Returns:
        bool: True if Storage Lens is available, False otherwise
    """
    try:
        # Create S3 Control client
        s3control_client = boto3.client('s3control', region_name='us-east-1')
        
        # Get caller identity for Account ID
        account_id = boto3.client('sts').get_caller_identity()["Account"]
        
        # List Storage Lens configurations
        response = s3control_client.list_storage_lens_configurations(
            AccountId=account_id
        )
        
        # Check if there are any Storage Lens configurations
        if 'StorageLensConfigurationList' in response and len(response['StorageLensConfigurationList']) > 0:
            print("Found S3 Storage Lens configurations. Will attempt to use for bucket metrics.")
            return True
        else:
            print("No S3 Storage Lens configurations found. Will use standard object counting for metrics.")
            return False
    except Exception as e:
        print(f"Error checking Storage Lens availability: {e}")
        print("Will use standard object counting for metrics.")
        return False

def get_latest_storage_lens_data(account_id):
    """
    Get the latest available Storage Lens data
    
    Args:
        account_id (str): AWS account ID
        
    Returns:
        dict: Dictionary mapping bucket names to their metrics
    """
    try:
        # Create S3 Control client
        s3control_client = boto3.client('s3control', region_name='us-east-1')
        
        # List Storage Lens configurations
        configurations = s3control_client.list_storage_lens_configurations(
            AccountId=account_id
        )
        
        if 'StorageLensConfigurationList' not in configurations or len(configurations['StorageLensConfigurationList']) == 0:
            return {}
            
        # Get the first configuration ID (default configuration if available)
        config_id = configurations['StorageLensConfigurationList'][0]['Id']
        
        # Create Athena client for querying Storage Lens data
        athena_client = boto3.client('athena', region_name='us-east-1')
        
        # Find the latest date with available data
        today = datetime.datetime.now()
        latest_data = {}
        
        # Try to get data for yesterday (Storage Lens data is available the next day)
        yesterday = today - datetime.timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
        
        # Try to get data from CloudWatch metrics as an alternative
        cw_client = boto3.client('cloudwatch', region_name='us-east-1')
        
        try:
            # Get a list of all buckets
            s3_client = boto3.client('s3')
            buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]
            
            for bucket_name in buckets:
                try:
                    # Get BucketSizeBytes metric
                    size_response = cw_client.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='BucketSizeBytes',
                        Dimensions=[
                            {'Name': 'BucketName', 'Value': bucket_name},
                            {'Name': 'StorageType', 'Value': 'StandardStorage'}
                        ],
                        StartTime=yesterday - datetime.timedelta(days=1),
                        EndTime=today,
                        Period=86400,
                        Statistics=['Average']
                    )
                    
                    # Get NumberOfObjects metric
                    objects_response = cw_client.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='NumberOfObjects',
                        Dimensions=[
                            {'Name': 'BucketName', 'Value': bucket_name},
                            {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                        ],
                        StartTime=yesterday - datetime.timedelta(days=1),
                        EndTime=today,
                        Period=86400,
                        Statistics=['Average']
                    )
                    
                    # Process metrics if available
                    size_bytes = 0
                    obj_count = 0
                    
                    if 'Datapoints' in size_response and len(size_response['Datapoints']) > 0:
                        size_bytes = size_response['Datapoints'][0]['Average']
                        
                    if 'Datapoints' in objects_response and len(objects_response['Datapoints']) > 0:
                        obj_count = int(objects_response['Datapoints'][0]['Average'])
                    
                    latest_data[bucket_name] = {
                        'size_bytes': size_bytes,
                        'object_count': obj_count
                    }
                    
                except Exception as e:
                    print(f"Error getting metrics for bucket {bucket_name}: {e}")
                    # Skip this bucket and continue
                    continue
            
        except Exception as e:
            print(f"Error getting CloudWatch metrics: {e}")
            # Fall back to empty data
            pass
        
        return latest_data
            
    except Exception as e:
        print(f"Error retrieving Storage Lens data: {e}")
        return {}

def convert_to_mb(size_in_bytes):
    """
    Convert bytes to megabytes
    
    Args:
        size_in_bytes (int or str): Size in bytes or "Not Available"
        
    Returns:
        float or str: Size in MB with 2 decimal places or "0" if not available
    """
    if size_in_bytes == "Not Available" or size_in_bytes == 0:
        return "0"
        
    # Convert bytes to MB (1 MB = 1024 * 1024 bytes)
    try:
        size_in_mb = float(size_in_bytes) / (1024 * 1024)
        return f"{size_in_mb:.2f}"
    except (ValueError, TypeError):
        return "0"

def get_s3_buckets_info(use_storage_lens=False):
    """
    Collect information about all S3 buckets across all regions
    
    Args:
        use_storage_lens (bool): Whether to try using Storage Lens for size metrics
        
    Returns:
        list: List of dictionaries containing bucket information
    """
    # Initialize global S3 client to list all buckets
    s3_client = boto3.client('s3')
    
    all_buckets_info = []
    storage_lens_data = {}
    
    # Get account ID
    account_id = boto3.client('sts').get_caller_identity()["Account"]
    
    # Try to get Storage Lens data if requested
    if use_storage_lens:
        storage_lens_data = get_latest_storage_lens_data(account_id)
    
    try:
        # Get the list of all buckets
        response = s3_client.list_buckets()
        
        total_buckets = len(response['Buckets'])
        print(f"\nFound {total_buckets} S3 buckets. Gathering details for each bucket...")
        
        # Process each bucket
        for i, bucket in enumerate(response['Buckets'], 1):
            bucket_name = bucket['Name']
            creation_date = bucket['CreationDate']
            
            print(f"Processing bucket {i}/{total_buckets}: {bucket_name}")
            
            # Get the bucket's region
            region = get_bucket_region(bucket_name)
            
            # Initialize size and object count
            size_bytes = 0
            object_count = 0
            
            # Try to get info from Storage Lens if available
            if bucket_name in storage_lens_data:
                size_bytes = storage_lens_data[bucket_name]['size_bytes']
                object_count = storage_lens_data[bucket_name]['object_count']
                size_source = "Storage Lens/CloudWatch"
            else:
                # Fall back to counting objects directly
                object_count = get_bucket_object_count(bucket_name, region)
                size_source = "Not Available"
            
            # Convert size to MB
            size_mb = convert_to_mb(size_bytes)
            
            # Add bucket info to our list
            bucket_info = {
                'Bucket Name': bucket_name,
                'Region': region,
                'Creation Date': creation_date,
                'Object Count': object_count,
                'Size (MB)': size_mb,
                'Size Source': size_source
            }
            
            all_buckets_info.append(bucket_info)
            
    except Exception as e:
        print(f"Error retrieving S3 bucket information: {e}")
    
    return all_buckets_info

def export_to_excel(buckets_info, account_name):
    """
    Export bucket information to an Excel file
    
    Args:
        buckets_info (list): List of dictionaries with bucket information
        account_name (str): Name of the AWS account for file naming
        
    Returns:
        str: Path to the created file
    """
    # Create a DataFrame from the bucket information
    df = pd.DataFrame(buckets_info)
    
    # Reorder columns for better readability
    column_order = [
        'Bucket Name', 
        'Region', 
        'Creation Date', 
        'Object Count',
        'Size (MB)',
        'Size Source'
    ]
    
    # Reorder columns (only include columns that exist in the DataFrame)
    available_columns = [col for col in column_order if col in df.columns]
    df = df[available_columns]
    
    # Format the creation date to be more readable
    if 'Creation Date' in df.columns:
        df['Creation Date'] = df['Creation Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate filename with current date
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create the full output path
    filename = output_dir / f"{account_name}-s3-buckets-inventory-{current_date}.xlsx"
    
    # Create Excel writer
    writer = pd.ExcelWriter(filename, engine='openpyxl')
    
    # Write data to Excel
    df.to_excel(writer, sheet_name='S3 Buckets', index=False)
    
    # Save the Excel file
    writer.close()
    
    print(f"\nData successfully exported to: {filename}")
    return filename

def export_to_csv(buckets_info, account_name):
    """
    Export bucket information to a CSV file
    
    Args:
        buckets_info (list): List of dictionaries with bucket information
        account_name (str): Name of the AWS account for file naming
        
    Returns:
        str: Path to the created file
    """
    # Create a DataFrame from the bucket information
    df = pd.DataFrame(buckets_info)
    
    # Reorder columns for better readability
    column_order = [
        'Bucket Name', 
        'Region', 
        'Creation Date', 
        'Object Count',
        'Size (MB)',
        'Size Source'
    ]
    
    # Reorder columns (only include columns that exist in the DataFrame)
    available_columns = [col for col in column_order if col in df.columns]
    df = df[available_columns]
    
    # Format the creation date to be more readable
    if 'Creation Date' in df.columns:
        df['Creation Date'] = df['Creation Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate filename with current date
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create the full output path
    filename = output_dir / f"{account_name}-s3-buckets-inventory-{current_date}.csv"
    
    # Write data to CSV
    df.to_csv(filename, index=False)
    
    print(f"\nData successfully exported to: {filename}")
    return filename

def main():
    """
    Main function to execute the script
    """
    # Print script title and get account information
    account_id, account_name = print_title()
    
    # Check if required dependencies are installed
    if not check_dependencies():
        return
    
    # Create argument parser
    parser = argparse.ArgumentParser(description='Export AWS S3 bucket information')
    parser.add_argument('--format', choices=['xlsx', 'csv'], default='xlsx',
                        help='Output format (xlsx or csv)')
    parser.add_argument('--skip-size', action='store_true',
                        help='Skip retrieving bucket sizes (faster)')
    
    # Parse arguments
    args = parser.parse_args()
    
    print("\nChecking for S3 Storage Lens availability...")
    use_storage_lens = check_storage_lens_availability()
    
    print("\nCollecting S3 bucket information across all regions...")
    print("This may take some time depending on the number of buckets...")
    
    # Get information about all S3 buckets
    buckets_info = get_s3_buckets_info(use_storage_lens=use_storage_lens)
    
    # Check if we found any buckets
    if not buckets_info:
        print("\nNo S3 buckets found or unable to retrieve bucket information.")
        return
    
    print(f"\nFound {len(buckets_info)} S3 buckets in total.")
    
    # Export the data to the selected format
    if args.format == 'xlsx':
        export_to_excel(buckets_info, account_name)
    else:
        export_to_csv(buckets_info, account_name)
    
    print("\nScript execution completed successfully.")

if __name__ == "__main__":
    main()