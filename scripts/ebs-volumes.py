#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EBS Volume Data Export
Version: v1.2.0
Date: SEP-30-2025

Description:
This script collects EBS volume information across AWS regions in an account and exports the data
to a spreadsheet file. The data includes volume ID, name, size, state, instance ID (if attached),
encryption status, and comprehensive volume metadata.

Features:
- Supports all standard AWS regions
- Comprehensive volume data export
- Cost calculation integration
- Flexible region filtering
- Enhanced error handling and logging
"""

import boto3
import os
import datetime
import csv
import sys
from pathlib import Path
import re

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
    
    Returns:
        bool: True if all dependencies are satisfied, False otherwise
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            utils.log_info(f"[OK] {package} is already installed")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        utils.log_warning(f"Packages required but not installed: {', '.join(missing_packages)}")
        response = input("Would you like to install these packages now? (y/n): ").lower()
        
        if response == 'y':
            import subprocess
            for package in missing_packages:
                utils.log_info(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    utils.log_success(f"Successfully installed {package}")
                except Exception as e:
                    utils.log_error(f"Error installing {package}", e)
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
        utils.log_error("Error getting account information", e)
        return "UNKNOWN", "UNKNOWN-ACCOUNT"

def get_aws_regions():
    """
    Get a list of available AWS regions.

    Returns:
        list: List of AWS region names
    """
    try:
        # Use utils function to get available AWS regions
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_default_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        return utils.get_default_regions()

def is_valid_aws_region(region_name):
    """
    Check if a region name is a valid AWS region.

    Args:
        region_name (str): The region name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return utils.is_aws_region(region_name)

def get_volume_name(volume):
    """
    Extract the volume name from tags.
    
    Args:
        volume (dict): The volume object from the API response
        
    Returns:
        str: The name of the volume or 'N/A' if not present
    """
    if 'Tags' in volume:
        for tag in volume['Tags']:
            if tag['Key'] == 'Name':
                return tag['Value']
    return 'N/A'

def format_tags(tags):
    """
    Format volume tags in the format "Key1:Value1, Key2:Value2, etc..."

    Args:
        tags (list): List of tag dictionaries with Key and Value

    Returns:
        str: Formatted tags string or 'N/A' if no tags
    """
    if not tags:
        return 'N/A'

    formatted_tags = []
    for tag in tags:
        if 'Key' in tag and 'Value' in tag:
            formatted_tags.append(f"{tag['Key']}:{tag['Value']}")

    if formatted_tags:
        return ', '.join(formatted_tags)
    else:
        return 'N/A'

def load_ebs_pricing_data():
    """
    Load EBS volume pricing data from the reference CSV file

    Returns:
        dict: Dictionary mapping volume types to price per GB per month
    """
    pricing_data = {}
    try:
        # Get the reference directory path relative to the script
        script_dir = Path(__file__).parent.absolute()
        pricing_file = script_dir.parent / 'reference' / 'ebsvol-pricing.csv'

        if not pricing_file.exists():
            utils.log_warning(f"Pricing file not found at {pricing_file}")
            return pricing_data

        with open(pricing_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                volume_type = row.get('Type', '').strip()
                price_str = row.get(' Cost per GB/month ', '').strip()

                if volume_type and price_str:
                    price = parse_ebs_price(price_str)
                    if price is not None:
                        pricing_data[volume_type] = price

        utils.log_info(f"Loaded pricing data for {len(pricing_data)} EBS volume types")
        return pricing_data

    except Exception as e:
        utils.log_warning(f"Error loading EBS pricing data: {e}")
        return pricing_data

def parse_ebs_price(price_str):
    """
    Parse EBS price string and return float value

    Args:
        price_str (str): Price string like "$0.08" or "$0.125"

    Returns:
        float or None: Parsed price per GB per month or None if unavailable
    """
    if not price_str or price_str.lower() in ['unavailable', 'n/a', '']:
        return None

    # Remove currency symbols, commas, and spaces
    cleaned = re.sub(r'[$,\s]', '', price_str)

    try:
        return float(cleaned)
    except ValueError:
        return None

def calculate_ebs_monthly_cost(volume_type, size_gb, state, pricing_data):
    """
    Calculate monthly cost for an EBS volume

    Args:
        volume_type (str): EBS volume type (e.g., 'gp3', 'gp2', 'io2')
        size_gb (int): Volume size in GB
        state (str): Volume state ('in-use', 'available', etc.)
        pricing_data (dict): Pricing data dictionary

    Returns:
        float or str: Monthly cost as a number or 'N/A' if unavailable
    """
    if volume_type not in pricing_data:
        return 'N/A'

    price_per_gb = pricing_data[volume_type]

    if price_per_gb is None:
        return 'N/A'

    # Calculate total monthly cost and return as number
    total_cost = price_per_gb * size_gb
    return round(total_cost, 2)

def get_ebs_volumes(region):
    """
    Get all EBS volumes in a specific AWS region.

    Args:
        region (str): AWS region name

    Returns:
        list: List of volume dictionaries with relevant information
    """
    # Validate region is AWS
    if not utils.is_aws_region(region):
        utils.log_error(f"Invalid AWS region: {region}")
        return []

    # Create a boto3 EC2 client for the specified AWS region
    ec2_client = boto3.client('ec2', region_name=region)

    # Initialize an empty list to store volume information
    volumes_data = []

    # Load EBS pricing data
    pricing_data = load_ebs_pricing_data()
    
    try:
        # Use pagination to handle large numbers of volumes
        paginator = ec2_client.get_paginator('describe_volumes')
        for page in paginator.paginate():
            for volume in page['Volumes']:
                # Initialize variables for volume data
                volume_name = get_volume_name(volume)
                instance_id = "Not attached"
                device_name = "N/A"
                attachment_state = "N/A"
                
                # Get attachment information if the volume is attached
                if volume['Attachments']:
                    attachment = volume['Attachments'][0]
                    instance_id = attachment['InstanceId']
                    device_name = attachment['Device']
                    attachment_state = attachment['State']
                
                # Get KMS key information for encrypted volumes
                kms_key_id = volume.get('KmsKeyId', 'N/A') if volume.get('Encrypted', False) else 'N/A'
                
                # Get IOPS information
                iops = volume.get('Iops', 'N/A')
                
                # Get throughput information (for gp3 volumes)
                throughput = volume.get('Throughput', 'N/A')
                
                # Get multi-attach enabled status
                multi_attach = 'Yes' if volume.get('MultiAttachEnabled', False) else 'No'
                
                # Format tags
                volume_tags = format_tags(volume.get('Tags', []))
                
                # Get owner information
                owner_id = utils.get_account_name_formatted(volume.get('OwnerId', 'N/A'))
                
                # Format creation time
                create_time = volume['CreateTime'].strftime('%Y-%m-%d %H:%M:%S') if 'CreateTime' in volume else 'N/A'

                # Calculate monthly cost
                monthly_cost = calculate_ebs_monthly_cost(
                    volume['VolumeType'],
                    volume['Size'],
                    volume['State'],
                    pricing_data
                )

                # Add volume data to the list with comprehensive information
                volumes_data.append({
                    'Region': region,
                    'Volume ID': volume['VolumeId'],
                    'Name': volume_name,
                    'Size (GB)': volume['Size'],
                    'Volume Type': volume['VolumeType'],
                    'Monthly Cost': monthly_cost,
                    'State': volume['State'],
                    'Attached To': instance_id,
                    'Device Name': device_name,
                    'Attachment State': attachment_state,
                    'IOPS': iops,
                    'Throughput (MiB/s)': throughput,
                    'Encrypted': 'Yes' if volume['Encrypted'] else 'No',
                    'KMS Key ID': kms_key_id,
                    'Multi-Attach': multi_attach,
                    'Create Time': create_time,
                    'Availability Zone': volume['AvailabilityZone'],
                    'Snapshot ID': volume.get('SnapshotId', 'N/A'),
                    'Owner ID': owner_id,
                    'Tags': volume_tags
                })
    except Exception as e:
        utils.log_error(f"Error getting volumes in region {region}", e)
    
    return volumes_data

def print_title():
    """
    Print a formatted title for the script.

    Returns:
        tuple: (account_id, account_name)
    """
    print("====================================================================")
    print("                   AWS RESOURCE SCANNER                            ")
    print("====================================================================")
    print("               AWS EBS VOLUME DATA EXPORT                         ")
    print("====================================================================")
    print("Version: v1.2.0                               Date: SEP-30-2025")
    print("Environment: AWS Commercial")
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
    suffix = "" if region_input == "all" else region_input

    # Generate filename using utils
    filename = utils.create_export_filename(
        account_name,
        "ebs-volumes",
        suffix,
        datetime.datetime.now().strftime("%m.%d.%Y")
    )

    # Save using the utility function
    saved_path = utils.save_dataframe_to_excel(df, filename)

    if saved_path:
        return saved_path
    else:
        # Fallback to direct save if utils function fails
        output_path = utils.get_output_filepath(filename)
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
        
        if account_name == "UNKNOWN-ACCOUNT":
            proceed = utils.prompt_for_confirmation("Unable to determine account name. Proceed anyway?", default=False)
            if not proceed:
                utils.log_info("Exiting script...")
                sys.exit(0)
        
        # Get AWS regions
        utils.log_info("Getting list of AWS regions...")
        all_regions = get_aws_regions()

        if not all_regions:
            utils.log_error("No AWS regions found. Please check your AWS credentials and permissions.")
            sys.exit(1)

        utils.log_info(f"Found {len(all_regions)} AWS regions: {', '.join(all_regions)}")
        
        # Prompt user for AWS region selection
        print("\nAWS Region Selection:")
        print("Would you like the information for all AWS regions or a specific region?")
        print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1, etc.")
        region_input = input("If all, write \"all\", or specify an AWS region name: ").strip().lower()
        
        # Determine which AWS regions to scan
        if region_input == "all":
            regions = all_regions
            utils.log_info("Collecting EBS data from all AWS regions...")
        else:
            # Validate the input region is an AWS region
            if is_valid_aws_region(region_input):
                regions = [region_input]
                utils.log_info(f"Collecting EBS data from AWS region: {region_input}")
            else:
                utils.log_warning(f"'{region_input}' is not a valid AWS region.")
                utils.log_info("Valid AWS regions include: us-east-1, us-west-1, us-west-2, eu-west-1")
                utils.log_info("Defaulting to all AWS regions...")
                regions = all_regions
                region_input = "all"
        
        # Initialize an empty list to store volume data from all regions
        all_volumes = []
        
        # Iterate through each AWS region and collect volume data
        for i, region in enumerate(regions):
            utils.log_info(f"Collecting EBS volume data from {region} ({i+1}/{len(regions)})...")
            try:
                # Get EBS volumes for the current AWS region
                region_volumes = get_ebs_volumes(region)
                all_volumes.extend(region_volumes)
                utils.log_info(f"  Found {len(region_volumes)} volumes in {region}.")
            except Exception as e:
                # Handle exceptions for regions that might not be accessible
                utils.log_error(f"Error collecting data from {region}", e)
        
        # Print summary of collected data
        utils.log_success(f"Total EBS volumes found across all AWS regions: {len(all_volumes)}")

        if not all_volumes:
            utils.log_warning("No volumes found in any AWS region. Exiting...")
            sys.exit(0)
        
        # Export data to Excel file
        utils.log_info("Exporting data to Excel format...")
        excel_path = create_excel_file(account_name, all_volumes, region_input)
        
        if excel_path:
            utils.log_success("AWS EBS volume data exported successfully!")
            utils.log_info(f"File location: {excel_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")
            utils.log_info(f"Total volumes exported: {len(all_volumes)}")
            print("\nScript execution completed.")
        else:
            utils.log_error("Error exporting data. Please check the logs.")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        utils.log_error("Unexpected error occurred", e)
        sys.exit(1)

if __name__ == "__main__":
    main()