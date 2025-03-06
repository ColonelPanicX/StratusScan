#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EBS Volume Data Export
Version: v1.1.0
Date: MAR-04-2025

Description: 
This script collects EBS volume information across all AWS regions in an account
and exports the data to a spreadsheet file. The data includes volume ID, name, size,
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

def check_dependencies():
    """
    Check if required dependencies are installed and offer to install them if missing.
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is already installed")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nPackages required but not installed: {', '.join(missing_packages)}")
        response = input("Would you like to install these packages now? (y/n): ").lower()
        
        if response == 'y':
            import subprocess
            for package in missing_packages:
                print(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ Successfully installed {package}")
                except Exception as e:
                    print(f"Error installing {package}: {e}")
                    print("Please install it manually with: pip install " + package)
                    return False
            return True
        else:
            print("Cannot proceed without required dependencies.")
            return False
    
    return True

def get_account_info():
    """
    Get the AWS account ID and name of the current session.
    
    Returns:
        tuple: (account_id, account_name)
    """
    try:
        # Create a boto3 STS client to get account information
        sts_client = boto3.client('sts')
        # Get the account ID from the STS GetCallerIdentity API call
        account_id = sts_client.get_caller_identity()["Account"]
        # Get account name from utils
        account_name = utils.get_account_name(account_id, default="UNKNOWN-ACCOUNT")
        return account_id, account_name
    except Exception as e:
        print(f"Error getting account information: {e}")
        return "UNKNOWN", "UNKNOWN-ACCOUNT"

def get_all_regions():
    """
    Get a list of all available AWS regions.
    
    Returns:
        list: List of region names
    """
    try:
        # Create a boto3 EC2 client to get region information
        ec2_client = boto3.client('ec2')
        # Describe all regions using the EC2 DescribeRegions API call
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        return []

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
    
    try:
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
    except Exception as e:
        print(f"Error getting volumes in region {region}: {e}")
    
    return volumes_data

def print_title():
    """
    Print a formatted title for the script.
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS EBS VOLUME DATA EXPORT")
    print("====================================================================")
    print("Version: v1.0.2                                 Date: MAR-04-2025")
    print("====================================================================")
    
    # Get account information
    account_id, account_name = get_account_info()
    
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    return account_id, account_name

def create_excel_file(account_name, volumes_data, region_input="all"):
    """
    Export volumes data to an Excel file using pandas.
    
    Args:
        account_name (str): Name of the AWS account
        volumes_data (list): List of dictionaries containing volume information
        region_input (str): Region specification for filename (default: "all")
        
    Returns:
        str: Path to the exported Excel file
    """
    # Import pandas here to avoid issues if it's not installed
    import pandas as pd
    
    # Convert data to pandas DataFrame
    df = pd.DataFrame(volumes_data)
    
    # Generate suffix based on region input
    suffix = "" if region_input == "all" else f"-{region_input}"
    
    # Generate filename using utils
    filename = utils.create_export_filename(
        account_name, 
        "ebs-volumes", 
        suffix, 
        datetime.datetime.now().strftime("%m.%d.%Y")
    )
    
    # Get full output path
    output_path = utils.get_output_filepath(filename)
    
    # Save using the utility function in utils.py
    saved_path = utils.save_dataframe_to_excel(df, filename)
    
    if saved_path:
        return saved_path
    else:
        # Fallback to direct save if utils function fails
        df.to_excel(output_path, index=False)
        return output_path

def main():
    """
    Main function to execute the script.
    """
    try:
        # Print the script title and get account information
        account_id, account_name = print_title()
        
        # Check for required dependencies
        if not check_dependencies():
            sys.exit(1)
            
        # Import pandas now that we've checked dependencies
        import pandas as pd
        
        # Get all available AWS regions
        print("\nGetting list of AWS regions...")
        all_regions = get_all_regions()
        
        if not all_regions:
            print("Error: No AWS regions found. Please check your AWS credentials and permissions.")
            sys.exit(1)
            
        print(f"Found {len(all_regions)} regions.")
        
        # Prompt user for region selection
        print("\nWould you like the information for all regions or a specific region?")
        region_input = input("If all, write \"all\", or if a specific region, write the region's name (ex. us-east-1): ").strip().lower()
        
        # Determine which regions to scan
        if region_input == "all":
            regions = all_regions
            print("\nCollecting EBS data from all regions...")
        else:
            # Validate the input region
            if region_input in all_regions:
                regions = [region_input]
                print(f"\nCollecting EBS data from region: {region_input}")
            else:
                print(f"\nWarning: '{region_input}' does not appear to be a valid region. Defaulting to all regions.")
                regions = all_regions
                print("\nCollecting EBS data from all regions...")
        
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
        print(f"\nTotal EBS volumes found across all regions: {len(all_volumes)}")
        
        if not all_volumes:
            print("No volumes found in any region. Exiting...")
            sys.exit(0)
        
        # Export data to Excel file
        print("Exporting data to Excel format...")
        excel_path = create_excel_file(account_name, all_volumes, region_input)
        print(f"Data exported to Excel: {excel_path}")
        
        print("Script execution completed.")
        
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
