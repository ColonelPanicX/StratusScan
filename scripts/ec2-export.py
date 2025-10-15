#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EC2 Instance Data Export Script
Version: v1.11.0
Date: SEP-30-2025

Description:
This script queries AWS EC2 instances across available regions and exports detailed instance
information to an Excel spreadsheet. The output filename includes the AWS account name based
on the account ID mapping in the configuration.

Features:
- Supports all standard AWS regions
- Comprehensive instance data export
- Cost calculation integration
- Flexible region filtering
- Enhanced error handling and logging
"""

import sys
import os
import boto3
import datetime
import csv
import time
from io import StringIO
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

def get_os_info_from_ssm(instance_id, region):
    """
    Retrieve detailed operating system information using SSM with timeout safeguards
    Returns the full OS version string or 'Unknown OS' if unavailable
    
    Note: SSM agent must be installed and running on the instance
    """
    try:
        ssm = boto3.client('ssm', region_name=region)
        
        # Check if the instance is managed by SSM
        response = ssm.describe_instance_information(
            Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
        )
        
        if not response['InstanceInformationList']:
            return "Unknown OS"
        
        # Get platform information from SSM
        instance_info = response['InstanceInformationList'][0]
        platform_type = instance_info.get('PlatformType', '')
        platform_name = instance_info.get('PlatformName', '')
        platform_version = instance_info.get('PlatformVersion', '')
        
        # If we have detailed platform info from SSM directly, use it
        if platform_name and platform_version:
            return f"{platform_name} {platform_version}"
        elif platform_name:
            return platform_name
            
        # If it's Windows, return basic Windows info
        if platform_type == 'Windows':
            return "Windows (Use AMI Name for details)"
        
        # For Linux, return basic Linux info
        return "Linux (Use AMI Name for details)"
        
    except Exception as e:
        utils.log_warning(f"SSM error for instance {instance_id} in region {region}: {e}")
        return "Unknown OS"

def get_instance_memory(ec2_client, instance_type):
    """
    Get RAM information for a given instance type using EC2 API
    Returns memory in MiB
    """
    try:
        response = ec2_client.describe_instance_types(InstanceTypes=[instance_type])
        if response['InstanceTypes']:
            return response['InstanceTypes'][0]['MemoryInfo']['SizeInMiB']
        return 'N/A'
    except Exception as e:
        utils.log_warning(f"Could not get memory info for instance type {instance_type}: {e}")
        return 'N/A'

def get_instance_stop_date(ec2_client, instance_id, state):
    """
    Get the date when an instance was stopped using state transition reason
    Returns the stop date or 'N/A' for running instances
    """
    if state != 'stopped':
        return 'N/A'
        
    try:
        # Get the state transition reason directly from instance metadata
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
        if response['Reservations']:
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['InstanceId'] == instance_id and instance.get('State', {}).get('Name') == 'stopped':
                        # Check the StateTransitionReason field
                        state_reason = instance.get('StateTransitionReason', '')
                        
                        # For user initiated shutdowns, the format is typically:
                        # "User initiated (YYYY-MM-DD HH:MM:SS GMT)"
                        if 'User initiated' in state_reason and '(' in state_reason and ')' in state_reason:
                            date_start = state_reason.find('(') + 1
                            date_end = state_reason.find(')')
                            if date_start > 0 and date_end > date_start:
                                return state_reason[date_start:date_end]
                        # For system or auto-scaling initiated stops, return the reason
                        elif state_reason:
                            return f"System initiated ({state_reason})"
        
        # If we couldn't get the stop date from the state reason, return unknown
        return 'Stopped (Date Unknown)'
        
    except Exception as e:
        utils.log_warning(f"Could not determine stop date for instance {instance_id}: {e}")
        return 'Stopped (Date Unknown)'

def get_os_info_from_ami(ec2_client, image_id, platform_details, platform):
    """
    Get detailed OS information from AMI metadata without making blocking calls
    
    Args:
        ec2_client: The boto3 EC2 client
        image_id (str): The AMI ID
        platform_details (str): The platform details from instance metadata
        platform (str): The platform from instance metadata
    
    Returns:
        str: Detailed operating system information where available
    """
    try:
        # Try to get AMI information (non-blocking)
        response = ec2_client.describe_images(ImageIds=[image_id])
        
        if response['Images']:
            image = response['Images'][0]
            
            # Check for Windows AMIs
            if platform == 'windows':
                description = image.get('Description', '')
                if description:
                    # Windows AMIs often contain the version in the description
                    return description
                name = image.get('Name', '')
                if name and 'Windows' in name:
                    return name
                return platform_details
            
            # For Linux AMIs
            name = image.get('Name', '')
            description = image.get('Description', '')
            
            # Amazon Linux AMIs
            if 'amzn' in name.lower() or 'amazon linux' in name.lower():
                return name if name else "Amazon Linux"
            
            # RHEL, Ubuntu, SUSE, etc.
            if any(distro in name.lower() or distro in description.lower() for distro in 
                   ['rhel', 'red hat', 'ubuntu', 'debian', 'suse', 'centos']):
                return name if name else description
            
            # If we have a name but don't recognize the distribution
            if name:
                return name
                
            # Fall back to description
            if description:
                return description
        
        # If AMI lookup fails, use platform details
        return platform_details
    
    except Exception as e:
        utils.log_warning(f"Could not get detailed OS info for AMI {image_id}: {e}")
        return platform_details

def format_tags(tags):
    """
    Format EC2 instance tags in the format "Key1:Value1, Key2:Value2, etc..."

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

def load_pricing_data():
    """
    Load EC2 pricing data from the reference CSV file

    Returns:
        dict: Dictionary mapping instance types to pricing data
    """
    pricing_data = {}
    try:
        # Get the reference directory path relative to the script
        script_dir = Path(__file__).parent.absolute()
        pricing_file = script_dir.parent / 'reference' / 'ec2-pricing.csv'

        if not pricing_file.exists():
            utils.log_warning(f"Pricing file not found at {pricing_file}")
            return pricing_data

        with open(pricing_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                instance_type = row.get('API Name', '').strip()
                if instance_type:
                    # Parse Linux pricing (On Demand Monthly)
                    linux_price_str = row.get(' On Demand (Monthly) ', '').strip()
                    linux_price = parse_price(linux_price_str)

                    # Parse Windows pricing (Windows On Demand cost Monthly)
                    windows_price_str = row.get(' Windows On Demand cost (Monthly) ', '').strip()
                    windows_price = parse_price(windows_price_str)

                    pricing_data[instance_type] = {
                        'linux': linux_price,
                        'windows': windows_price
                    }

        utils.log_info(f"Loaded pricing data for {len(pricing_data)} instance types")
        return pricing_data

    except Exception as e:
        utils.log_warning(f"Error loading pricing data: {e}")
        return pricing_data

def load_storage_pricing_data():
    """
    Load EBS volume pricing data from the reference CSV file

    Returns:
        dict: Dictionary mapping volume types to cost per GB/month
    """
    storage_pricing = {}
    try:
        # Get the reference directory path relative to the script
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

def calculate_monthly_cost(instance_type, platform, state, pricing_data):
    """
    Calculate monthly cost for an EC2 instance

    Args:
        instance_type (str): EC2 instance type (e.g., 't3.micro')
        platform (str): Platform type ('windows' or Linux/UNIX)
        state (str): Instance state ('running', 'stopped', etc.)
        pricing_data (dict): Pricing data dictionary

    Returns:
        float or str: Numeric monthly cost value or 'N/A'
    """
    # Only calculate cost for running instances
    if state != 'running':
        return 0.00

    if instance_type not in pricing_data:
        return 'N/A'

    # Determine platform for pricing lookup
    is_windows = platform and platform.lower() == 'windows'
    price_key = 'windows' if is_windows else 'linux'

    price = pricing_data[instance_type].get(price_key)

    if price is None:
        return 'N/A'

    return price

def get_attached_volumes(ec2_client, instance):
    """
    Get all attached volumes for an instance, excluding the root volume

    Args:
        ec2_client: The boto3 EC2 client
        instance: The instance object

    Returns:
        tuple: (list of volume IDs, dict of volume info with size and type)
    """
    attached_volumes = []
    volume_info = {}
    root_device_name = instance.get('RootDeviceName')

    try:
        for device in instance.get('BlockDeviceMappings', []):
            device_name = device.get('DeviceName')
            volume_id = device.get('Ebs', {}).get('VolumeId')

            # Skip root device
            if device_name == root_device_name:
                continue

            if volume_id:
                attached_volumes.append(volume_id)

                # Get volume details
                try:
                    volumes = ec2_client.describe_volumes(VolumeIds=[volume_id])
                    if volumes and 'Volumes' in volumes and len(volumes['Volumes']) > 0:
                        vol = volumes['Volumes'][0]
                        volume_info[volume_id] = {
                            'size': vol.get('Size', 0),
                            'type': vol.get('VolumeType', 'standard')
                        }
                except Exception as e:
                    utils.log_warning(f"Error getting volume info for {volume_id}: {e}")
                    volume_info[volume_id] = {'size': 0, 'type': 'standard'}

    except Exception as e:
        utils.log_warning(f"Error getting attached volumes: {e}")

    return attached_volumes, volume_info

def calculate_storage_cost(root_size, root_type, attached_volume_info, storage_pricing):
    """
    Calculate total monthly storage cost for all volumes

    Args:
        root_size (int): Size of root volume in GiB
        root_type (str): Type of root volume (gp3, gp2, etc.)
        attached_volume_info (dict): Dictionary of volume IDs to their info (size, type)
        storage_pricing (dict): Storage pricing data

    Returns:
        float or str: Total monthly storage cost or 'N/A'
    """
    try:
        total_cost = 0.0

        # Calculate root volume cost
        if root_size != 'N/A' and root_type != 'N/A':
            root_price = storage_pricing.get(root_type, storage_pricing.get('gp3', 0.08))
            total_cost += float(root_size) * root_price

        # Calculate attached volumes cost
        for vol_id, vol_info in attached_volume_info.items():
            vol_size = vol_info.get('size', 0)
            vol_type = vol_info.get('type', 'gp3')
            vol_price = storage_pricing.get(vol_type, storage_pricing.get('gp3', 0.08))
            total_cost += float(vol_size) * vol_price

        return round(total_cost, 2)

    except Exception as e:
        utils.log_warning(f"Error calculating storage cost: {e}")
        return 'N/A'

def check_dependencies():
    """Check and install required dependencies if user agrees"""
    required_packages = ['pandas', 'openpyxl', 'boto3']
    
    for package in required_packages:
        try:
            __import__(package)
            utils.log_info(f"[OK] {package} is already installed")
        except ImportError:
            print(f"\nPackage '{package}' is required but not installed.")
            response = input(f"Would you like to install {package}? (y/n): ").lower()
            
            if response == 'y':
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

def get_account_info():
    """Retrieve AWS account ID and map it to account name"""
    try:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        account_name = utils.get_account_name(account_id, default="UNKNOWN-ACCOUNT")
        return account_id, account_name
    except Exception as e:
        utils.log_error("Error getting account information", e)
        return "UNKNOWN", "UNKNOWN-ACCOUNT"

def get_aws_regions():
    """Get list of available AWS regions"""
    try:
        # Use utils function to get AWS regions
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_default_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        return utils.get_default_regions()

def is_valid_aws_region(region_name):
    """Check if a region name is a valid AWS region"""
    return utils.is_aws_region(region_name)

def get_instance_data(region, instance_filter=None):
    """
    Retrieve EC2 instance data for a specific AWS region

    Args:
        region (str): AWS region name
        instance_filter (str, optional): Filter by instance state ('running', 'stopped', or None for all)
    """
    # Validate region is AWS
    if not utils.is_aws_region(region):
        utils.log_error(f"Invalid AWS region: {region}")
        return []

    ec2 = boto3.client('ec2', region_name=region)
    instances = []

    # Load pricing data
    pricing_data = load_pricing_data()
    storage_pricing = load_storage_pricing_data()
    
    try:
        # Prepare filters if needed
        filters = []
        if instance_filter:
            filters.append({
                'Name': 'instance-state-name',
                'Values': [instance_filter]
            })
        
        # Get instances in the region with optional filter
        if filters:
            response = ec2.describe_instances(Filters=filters)
        else:
            response = ec2.describe_instances()
        
        # Count total instances first for progress tracking
        total_instances = 0
        for reservation in response['Reservations']:
            total_instances += len(reservation['Instances'])

        if total_instances > 0:
            utils.log_info(f"Found {total_instances} instances in {region} to process")

        processed = 0
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                processed += 1
                instance_id = instance.get('InstanceId', 'Unknown')
                progress = (processed / total_instances) * 100 if total_instances > 0 else 0

                utils.log_info(f"[{progress:.1f}%] Processing instance {processed}/{total_instances}: {instance_id}")
                # Get the root volume information
                root_device = next((device for device in instance.get('BlockDeviceMappings', [])
                                  if device['DeviceName'] == instance.get('RootDeviceName')), None)
                
                # Get detailed OS information
                os_info = get_os_info_from_ssm(instance.get('InstanceId', ''), region)
                
                # Get AMI name information
                ami_name = get_os_info_from_ami(
                    ec2,
                    instance.get('ImageId', ''),
                    instance.get('PlatformDetails', 'N/A'),
                    instance.get('Platform', '')
                )
                
                # Get RAM info based on instance type
                instance_type = instance.get('InstanceType', 'N/A')
                ram_mib = get_instance_memory(ec2, instance_type)
                
                # For root device size and type, we need to ensure we're fetching it correctly
                root_device_size = 'N/A'
                root_volume_id = 'N/A'
                root_volume_type = 'N/A'

                if root_device:
                    root_volume_id = root_device.get('Ebs', {}).get('VolumeId', 'N/A')
                    # If we have the volume ID, we can get its size and type
                    if root_volume_id != 'N/A':
                        try:
                            volumes = ec2.describe_volumes(VolumeIds=[root_volume_id])
                            if volumes and 'Volumes' in volumes and len(volumes['Volumes']) > 0:
                                root_device_size = volumes['Volumes'][0].get('Size', 'N/A')
                                root_volume_type = volumes['Volumes'][0].get('VolumeType', 'N/A')
                        except Exception as e:
                            utils.log_warning(f"Error getting volume info for {root_volume_id}: {e}")
                    else:
                        # Try to get size from the device mapping directly
                        root_device_size = root_device.get('Ebs', {}).get('VolumeSize', 'N/A')

                # Get attached volumes (non-root)
                attached_vols, attached_vol_info = get_attached_volumes(ec2, instance)
                attached_volumes_str = ', '.join(attached_vols) if attached_vols else 'N/A'
                
                # Get instance state and stopped date if applicable
                instance_state = instance.get('State', {}).get('Name', 'N/A')
                stop_date = get_instance_stop_date(ec2, instance.get('InstanceId', ''), instance_state)
                
                # Format tags
                instance_tags = format_tags(instance.get('Tags', []))

                # Calculate monthly cost
                monthly_cost = calculate_monthly_cost(
                    instance.get('InstanceType', 'N/A'),
                    instance.get('Platform', 'Linux/UNIX'),
                    instance_state,
                    pricing_data
                )

                # Calculate storage cost
                storage_cost = calculate_storage_cost(
                    root_device_size,
                    root_volume_type,
                    attached_vol_info,
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

                # Extract instance information
                instance_data = {
                    'Computer Name': next((tag['Value'] for tag in instance.get('Tags', [])
                                        if tag['Key'] == 'Name'), 'N/A'),
                    'Instance ID': instance.get('InstanceId', 'N/A'),
                    'State': instance_state,
                    'Stopped Date': stop_date,
                    'Instance Type': instance.get('InstanceType', 'N/A'),
                    'Platform': instance.get('Platform', 'Linux/UNIX'),
                    'Monthly Cost (On-Demand)': monthly_cost,
                    'Monthly Storage Cost': storage_cost,
                    'Total Monthly Cost': total_monthly_cost,
                    'Operating System': os_info,
                    'AMI Name': ami_name,
                    'Private IPv4': instance.get('PrivateIpAddress', 'N/A'),
                    'Public IPv4': instance.get('PublicIpAddress', 'N/A'),
                    'IPv6': next((
                        next((addr.get('Ipv6Address', 'N/A')
                             for addr in interface.get('Ipv6Addresses', [])), 'N/A')
                        for interface in instance.get('NetworkInterfaces', [])
                    ), 'N/A'),
                    'VPC ID': instance.get('VpcId', 'N/A'),
                    'Subnet ID': instance.get('SubnetId', 'N/A'),
                    'Availability Zone': instance.get('Placement', {}).get('AvailabilityZone', 'N/A'),
                    'AMI ID': instance.get('ImageId', 'N/A'),
                    'Launch Time': instance.get('LaunchTime', 'N/A'),
                    'Key Pair': instance.get('KeyName', 'N/A'),
                    'Region': region,
                    'Owner ID': utils.get_account_name_formatted(instance.get('OwnerId', 'N/A')),
                    'vCPU': instance.get('CpuOptions', {}).get('CoreCount', 'N/A'),
                    'RAM (MiB)': ram_mib,
                    'Root Device Volume ID': root_volume_id,
                    'Root Device Size (GiB)': root_device_size,
                    'Attached Volumes': attached_volumes_str,
                    'Tags': instance_tags
                }
                instances.append(instance_data)

                # Small delay to avoid API throttling
                if processed < total_instances:  # Don't delay after the last instance
                    time.sleep(0.1)
                
    except Exception as e:
        utils.log_error(f"Error getting instances in region {region}", e)
    
    return instances

def main():
    """Main function to execute the script"""
    try:
        # Check for required dependencies
        check_dependencies()
        
        # Import pandas after dependency check
        import pandas as pd
        
        # Get account information
        utils.log_info("Getting AWS account information...")
        account_id, account_name = get_account_info()

        # Print script header
        print("\n====================================================================")
        print("                   AWS RESOURCE SCANNER                            ")
        print("====================================================================")
        print("                  AWS EC2 INSTANCES DATA EXPORT                   ")
        print("====================================================================")
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
        print(f"Environment: AWS Commercial")
        print("====================================================================\n")
        
        if account_name == "UNKNOWN-ACCOUNT":
            proceed = input("Unable to determine account name. Proceed anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Exiting script...")
                sys.exit(0)
        
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")
        
        # Get instance state filter preference
        print("Choose one of the following (enter the corresponding number):")
        print("1. Export all instances")
        print("2. Export only running instances")
        print("3. Export only stopped instances")
        
        while True:
            filter_choice = input("Enter your choice (1-3): ")
            if filter_choice in ["1", "2", "3"]:
                break
            print("Invalid choice. Please enter 1, 2, or 3.")
        
        # Set instance filter based on user choice
        instance_filter = None
        filter_desc = "all"  # Default for filename
        if filter_choice == "2":
            instance_filter = "running"
            filter_desc = "running"
        elif filter_choice == "3":
            instance_filter = "stopped"
            filter_desc = "stopped"
        
        # Get AWS region preference
        print("\nAWS Region Selection:")
        print("Would you like the information for all AWS regions or a specific region?")
        print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1, etc.")
        region_choice = input("If all, write \"all\", or specify an AWS region name: ").lower().strip()

        if region_choice != "all":
            if not is_valid_aws_region(region_choice):
                utils.log_warning(f"'{region_choice}' is not a valid AWS region.")
                utils.log_info("Valid AWS regions include: us-east-1, us-west-1, us-west-2, eu-west-1")
                utils.log_info("Checking all available AWS regions instead.")
                region_choice = "all"
        
        # Get AWS regions to scan
        if region_choice == "all":
            utils.log_info("Retrieving available AWS regions...")
            regions = get_aws_regions()
            if not regions:
                utils.log_error("No AWS regions found. Please check your AWS credentials and permissions.")
                sys.exit(1)
            utils.log_info(f"Found {len(regions)} AWS regions to scan: {', '.join(regions)}")
        else:
            regions = [region_choice]
            utils.log_info(f"Scanning only the {region_choice} AWS region.")
        
        # Collect instance data from specified AWS regions
        all_instances = []
        total_instances = 0
        for region in regions:
            utils.log_info(f"Collecting data from AWS region: {region}")
            instances = get_instance_data(region, instance_filter)
            instance_count = len(instances)
            total_instances += instance_count
            utils.log_info(f"Found {instance_count} instances in {region}")
            all_instances.extend(instances)

        if not all_instances:
            utils.log_warning("No instances found in any AWS region. Exiting...")
            sys.exit(0)

        utils.log_success(f"Total EC2 Instances found across all AWS regions: {total_instances}")
        
        # Create DataFrame and handle timezone-aware datetimes
        utils.log_info("Preparing data for export to Excel format...")
        df = pd.DataFrame(all_instances)
        
        # Convert Launch Time to timezone-naive datetime
        df['Launch Time'] = pd.to_datetime(df['Launch Time']).dt.tz_localize(None)
        
        # Generate filename with filter and region info
        region_desc = "" if region_choice == "all" else f"-{region_choice}"
        
        # Use utils module to generate filename and save data
        filename = utils.create_export_filename(
            account_name,
            "ec2",
            f"{filter_desc}{region_desc}",
            current_date
        )
        
        # Save data using the utility function
        output_path = utils.save_dataframe_to_excel(df, filename)
        
        if output_path:
            utils.log_success(f"AWS EC2 data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")
            utils.log_info(f"Total instances exported: {total_instances}")
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
