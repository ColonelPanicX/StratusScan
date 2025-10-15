#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EBS Snapshots Export Tool
Version: v1.0.0
Date: MAR-04-2025

Description:
This script exports Amazon EBS snapshot information across all AWS regions or a specific
region into an Excel spreadsheet. The export includes snapshot name, ID, description,
size information, encryption status, storage tier, and creation date.
"""

import sys
import os
import boto3
import datetime
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
    Print the title banner and get account information.
    
    Returns:
        tuple: (account_id, account_name)
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS EBS SNAPSHOTS EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.0.0                                 Date: MAR-04-2025")
    print("====================================================================")
    
    # Get the current AWS account ID
    try:
        # Create a new STS client to get the current account ID
        sts_client = boto3.client('sts')
        # Get account ID from caller identity
        account_id = sts_client.get_caller_identity()['Account']
        # Map the account ID to an account name using utils module
        account_name = utils.get_account_name(account_id, default=account_id)
        
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print(f"Could not determine account information: {e}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    print("====================================================================")
    return account_id, account_name

def check_dependencies():
    """
    Check if required dependencies are installed and offer to install them if missing.
    
    Returns:
        bool: True if all dependencies are satisfied, False otherwise
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

def get_all_regions():
    """
    Get a list of all available AWS regions.
    
    Returns:
        list: List of region names
    """
    try:
        # Create an EC2 client to get all available regions
        ec2_client = boto3.client('ec2')
        # Get all regions using the EC2 DescribeRegions API call
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        # Return a default list of common regions if API call fails
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1'
        ]

def is_valid_region(region_name):
    """
    Check if a region name is valid.
    
    Args:
        region_name (str): The region name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    all_regions = get_all_regions()
    return region_name in all_regions

def get_snapshot_name(snapshot):
    """
    Extract the snapshot name from tags.
    
    Args:
        snapshot (dict): The snapshot object from the API response
        
    Returns:
        str: The name of the snapshot or 'N/A' if not present
    """
    if 'Tags' in snapshot:
        for tag in snapshot['Tags']:
            if tag['Key'] == 'Name':
                return tag['Value']
    return 'N/A'

def get_snapshots(region):
    """
    Get all EBS snapshots owned by the account in a specific region.
    
    Args:
        region (str): AWS region name
        
    Returns:
        list: List of dictionaries with snapshot information
    """
    snapshots_data = []
    
    try:
        # Create an EC2 client for the specified region
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Use pagination to handle large number of snapshots
        paginator = ec2_client.get_paginator('describe_snapshots')
        page_iterator = paginator.paginate(OwnerIds=['self'])
        
        for page in page_iterator:
            for snapshot in page['Snapshots']:
                # Get snapshot name from tags
                snapshot_name = get_snapshot_name(snapshot)
                
                # Extract standard snapshot attributes
                snapshot_id = snapshot['SnapshotId']
                volume_id = snapshot.get('VolumeId', 'N/A')
                description = snapshot.get('Description', 'N/A')
                volume_size = snapshot.get('VolumeSize', 0)  # Size in GB
                
                # Handle start time (convert to string without timezone)
                start_time = snapshot.get('StartTime', '')
                start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A'
                
                # Get encryption status
                encryption = 'Yes' if snapshot.get('Encrypted', False) else 'No'
                
                # Get storage tier (Standard or Archive)
                storage_tier = snapshot.get('StorageTier', 'Standard')
                
                # Additional data processing for specific attributes
                # Full snapshot size is reported in bytes if available, convert to GB
                full_snapshot_size_bytes = snapshot.get('DataEncryptionKeyId', 0)  # This field doesn't exist, but keeping the structure
                full_snapshot_size_gb = 'N/A'  # Usually not available via standard API
                
                # Add to results
                snapshots_data.append({
                    'Name': snapshot_name,
                    'Snapshot ID': snapshot_id,
                    'Volume ID': volume_id,
                    'Description': description,
                    'Volume Size (GB)': volume_size,
                    'Full Snapshot Size': full_snapshot_size_gb,
                    'Storage Tier': storage_tier,
                    'Started': start_time_str,
                    'Encryption': encryption,
                    'Region': region
                })
                
    except Exception as e:
        print(f"Error getting snapshots in region {region}: {e}")
    
    return snapshots_data

def main():
    """
    Main function to execute the script.
    """
    try:
        # Print title and get account information
        account_id, account_name = print_title()
        
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Now import pandas (after dependency check)
        import pandas as pd
        
        # Get region preference from user
        print("\nWould you like the information for all regions or a specific region?")
        region_choice = input("If all, write \"all\", and if a specific region, write the region's name (ex. us-east-1): ").strip().lower()
        
        if region_choice != "all":
            if not is_valid_region(region_choice):
                print(f"Warning: '{region_choice}' is not a valid AWS region. Checking all regions instead.")
                region_choice = "all"
        
        # Determine regions to process
        if region_choice == "all":
            print("\nRetrieving AWS regions...")
            regions = get_all_regions()
            if not regions:
                print("Error: No AWS regions found. Please check your AWS credentials and permissions.")
                sys.exit(1)
            print(f"Found {len(regions)} regions to scan.")
        else:
            regions = [region_choice]
            print(f"\nScanning only the {region_choice} region.")
        
        # Collect snapshot data from all specified regions
        all_snapshots = []
        total_regions = len(regions)
        
        for i, region in enumerate(regions, 1):
            progress = (i / total_regions) * 100
            print(f"[{progress:.1f}%] Processing region: {region} ({i}/{total_regions})")
            
            region_snapshots = get_snapshots(region)
            all_snapshots.extend(region_snapshots)
            
            print(f"  Found {len(region_snapshots)} snapshots in {region}")
            
            # Add a small delay to avoid API throttling
            time.sleep(0.5)
        
        # Print summary
        total_snapshots = len(all_snapshots)
        print(f"\nTotal snapshots found across all regions: {total_snapshots}")
        
        if total_snapshots == 0:
            print("No snapshots found. Nothing to export.")
            sys.exit(0)
        
        # Create DataFrame from snapshot data
        df = pd.DataFrame(all_snapshots)
        
        # Generate filename with region info
        region_suffix = "" if region_choice == "all" else f"-{region_choice}"
        
        # Use utils module to generate filename
        filename = utils.create_export_filename(
            account_name, 
            "ebs-snapshots", 
            region_suffix, 
            datetime.datetime.now().strftime("%m.%d.%Y")
        )
        
        # Save the data using the utility function
        output_path = utils.save_dataframe_to_excel(df, filename)
        
        if output_path:
            print(f"\nData exported successfully to: {output_path}")
            print("Script execution completed.")
        else:
            print("\nError exporting data. Please check the logs.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
