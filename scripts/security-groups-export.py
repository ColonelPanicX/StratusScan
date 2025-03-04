#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Security Groups Export Script
Version: v1.1.0
Date: MAR-03-2025

Description:
This script exports security group information from all AWS regions
including group name, ID, VPC, inbound rules, outbound rules, and associated resources.
Each security group rule is listed on its own line for better analysis and filtering.
The data is exported to an Excel file with all security groups in a single sheet.

"""

import boto3
import sys
import os
import datetime
import time
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
    Check and install dependencies if necessary
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
        print(f"Missing required packages: {', '.join(missing_packages)}")
        install = input("Would you like to install them now? (y/n): ").lower()
        
        if install == 'y':
            import subprocess
            for package in missing_packages:
                try:
                    print(f"Installing {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to install {package}: {e}")
                    print("Please install the package manually and try again.")
                    sys.exit(1)
        else:
            print("Cannot continue without required packages. Exiting.")
            sys.exit(1)
    
    # Import packages now that they're installed
    global pd
    import pandas as pd

def get_account_info():
    """
    Get the current AWS account ID and name
    """
    try:
        # Get the account ID
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        
        # Map the account ID to a name using the utils module
        account_name = utils.get_account_name(account_id, default=f"UNKNOWN-{account_id}")
        
        return account_id, account_name
    except Exception as e:
        print(f"Error getting account information: {e}")
        return "Unknown", "Unknown-Account"

def print_title():
    """
    Print the script title and account information
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS SECURITY GROUPS EXPORT")
    print("====================================================================")
    
    # Get account information
    account_id, account_name = get_account_info()
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    
    return account_id, account_name

def get_all_regions():
    """
    Get a list of all available AWS regions
    """
    try:
        ec2_client = boto3.client('ec2')
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        print("Using default list of regions.")
        # Fallback to common regions if we can't get the full list
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1'
        ]

def get_vpc_name(ec2_client, vpc_id):
    """
    Get the name of a VPC from its ID
    """
    if not vpc_id:
        return "No VPC (EC2-Classic)"
    
    try:
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        
        if not response['Vpcs']:
            return vpc_id  # Return the ID if no VPC found
        
        # Look for the Name tag
        for tag in response['Vpcs'][0].get('Tags', []):
            if tag['Key'] == 'Name':
                return f"{tag['Value']} ({vpc_id})"
        
        # If no Name tag, just return the ID
        return vpc_id
    except Exception as e:
        return vpc_id  # Return the ID on error

def format_ip_range(ip_range, protocol, from_port, to_port, is_inbound=True):
    """
    Format IP range rule details
    """
    if protocol == '-1':
        protocol = 'All'
    
    # Format port range
    port_range = ''
    if from_port is not None and to_port is not None:
        if from_port == to_port:
            port_range = str(from_port)
        else:
            port_range = f"{from_port}-{to_port}"
    else:
        port_range = 'All'
    
    # Format CIDR
    cidr = ip_range.get('CidrIp', ip_range.get('CidrIpv6', 'Unknown'))
    
    if is_inbound:
        return f"{cidr} → {protocol}:{port_range}"
    else:
        return f"{protocol}:{port_range} → {cidr}"

def format_security_group_reference(sg_ref, protocol, from_port, to_port, is_inbound=True):
    """
    Format security group reference rule details
    """
    if protocol == '-1':
        protocol = 'All'
    
    # Format port range
    port_range = ''
    if from_port is not None and to_port is not None:
        if from_port == to_port:
            port_range = str(from_port)
        else:
            port_range = f"{from_port}-{to_port}"
    else:
        port_range = 'All'
    
    # Format security group reference
    sg_identifier = ""
    if 'GroupId' in sg_ref:
        sg_identifier = f"sg:{sg_ref['GroupId']}"
    elif 'GroupName' in sg_ref:
        sg_identifier = f"sg:{sg_ref['GroupName']}"
    else:
        sg_identifier = "sg:Unknown"
    
    if is_inbound:
        return f"{sg_identifier} → {protocol}:{port_range}"
    else:
        return f"{protocol}:{port_range} → {sg_identifier}"

def get_security_group_resources(ec2_client, sg_id):
    """
    Find EC2 instances, RDS instances, and other resources using this security group
    """
    resources = []
    
    # Check EC2 instances
    try:
        response = ec2_client.describe_instances(
            Filters=[{'Name': 'instance.group-id', 'Values': [sg_id]}]
        )
        
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                # Get instance name from tags
                instance_name = 'Unnamed'
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break
                
                resources.append(f"EC2:{instance_name} ({instance['InstanceId']})")
    except Exception as e:
        pass  # Silently continue if we can't get EC2 instances
    
    # Try to check RDS instances
    try:
        rds_client = boto3.client('rds', region_name=ec2_client.meta.region_name)
        response = rds_client.describe_db_instances()
        
        for instance in response.get('DBInstances', []):
            for sg in instance.get('VpcSecurityGroups', []):
                if sg.get('VpcSecurityGroupId') == sg_id:
                    resources.append(f"RDS:{instance['DBInstanceIdentifier']}")
                    break
    except Exception as e:
        pass  # Silently continue if we can't get RDS instances
    
    # Try to check ELBs (Classic Load Balancers)
    try:
        elb_client = boto3.client('elb', region_name=ec2_client.meta.region_name)
        response = elb_client.describe_load_balancers()
        
        for lb in response.get('LoadBalancerDescriptions', []):
            if sg_id in lb.get('SecurityGroups', []):
                resources.append(f"ELB:{lb['LoadBalancerName']}")
    except Exception as e:
        pass  # Silently continue if we can't get ELBs
    
    # Try to check ELBv2 (Application and Network Load Balancers)
    try:
        elbv2_client = boto3.client('elbv2', region_name=ec2_client.meta.region_name)
        response = elbv2_client.describe_load_balancers()
        
        for lb in response.get('LoadBalancers', []):
            if sg_id in lb.get('SecurityGroups', []):
                resources.append(f"ALB/NLB:{lb['LoadBalancerName']}")
    except Exception as e:
        pass  # Silently continue if we can't get ALBs/NLBs
    
    # Try to check Lambda functions
    try:
        lambda_client = boto3.client('lambda', region_name=ec2_client.meta.region_name)
        response = lambda_client.list_functions()
        
        for function in response.get('Functions', []):
            if 'VpcConfig' in function and sg_id in function['VpcConfig'].get('SecurityGroupIds', []):
                resources.append(f"Lambda:{function['FunctionName']}")
    except Exception as e:
        pass  # Silently continue if we can't get Lambda functions
    
    return resources

def get_security_group_rules(region):
    """
    Get all security groups and their rules from a specific region
    """
    security_group_rules = []
    
    try:
        # Create EC2 client for this region
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get all security groups
        response = ec2_client.describe_security_groups()
        
        # Counter for generating unique rule IDs
        rule_counter = 0
        
        for sg in response.get('SecurityGroups', []):
            sg_id = sg['GroupId']
            sg_name = sg.get('GroupName', 'Unnamed')
            
            # Get VPC name if available
            vpc_id = sg.get('VpcId', '')
            vpc_name = get_vpc_name(ec2_client, vpc_id) if vpc_id else "No VPC (EC2-Classic)"
            
            # Get resources using this security group
            resources = get_security_group_resources(ec2_client, sg_id)
            resources_str = '; '.join(resources) if resources else 'None'
            
            # Get description
            description = sg.get('Description', '')
            
            # Process inbound rules (IpPermissions)
            for permission in sg.get('IpPermissions', []):
                protocol = permission.get('IpProtocol', 'All')
                from_port = permission.get('FromPort', None)
                to_port = permission.get('ToPort', None)
                
                # Process IPv4 ranges
                for ip_range in permission.get('IpRanges', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = ip_range.get('Description', '')
                    
                    rule_text = format_ip_range(ip_range, protocol, from_port, to_port, is_inbound=True)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Inbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'CIDR': ip_range.get('CidrIp', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
                
                # Process IPv6 ranges
                for ip_range in permission.get('Ipv6Ranges', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = ip_range.get('Description', '')
                    
                    rule_text = format_ip_range(ip_range, protocol, from_port, to_port, is_inbound=True)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Inbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'CIDR': ip_range.get('CidrIpv6', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
                
                # Process security group references
                for sg_ref in permission.get('UserIdGroupPairs', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = sg_ref.get('Description', '')
                    
                    rule_text = format_security_group_reference(sg_ref, protocol, from_port, to_port, is_inbound=True)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Inbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'Referenced SG': sg_ref.get('GroupId', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
            
            # Process outbound rules (IpPermissionsEgress)
            for permission in sg.get('IpPermissionsEgress', []):
                protocol = permission.get('IpProtocol', 'All')
                from_port = permission.get('FromPort', None)
                to_port = permission.get('ToPort', None)
                
                # Process IPv4 ranges
                for ip_range in permission.get('IpRanges', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = ip_range.get('Description', '')
                    
                    rule_text = format_ip_range(ip_range, protocol, from_port, to_port, is_inbound=False)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Outbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'CIDR': ip_range.get('CidrIp', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
                
                # Process IPv6 ranges
                for ip_range in permission.get('Ipv6Ranges', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = ip_range.get('Description', '')
                    
                    rule_text = format_ip_range(ip_range, protocol, from_port, to_port, is_inbound=False)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Outbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'CIDR': ip_range.get('CidrIpv6', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
                
                # Process security group references
                for sg_ref in permission.get('UserIdGroupPairs', []):
                    rule_counter += 1
                    rule_id = f"R{rule_counter}"
                    rule_desc = sg_ref.get('Description', '')
                    
                    rule_text = format_security_group_reference(sg_ref, protocol, from_port, to_port, is_inbound=False)
                    
                    security_group_rules.append({
                        'Rule ID': rule_id,
                        'SG Name': sg_name,
                        'SG ID': sg_id,
                        'VPC': vpc_name,
                        'SG Description': description,
                        'Direction': 'Outbound',
                        'Rule': rule_text,
                        'Rule Description': rule_desc,
                        'Protocol': protocol if protocol != '-1' else 'All',
                        'From Port': from_port if from_port is not None else 'All',
                        'To Port': to_port if to_port is not None else 'All',
                        'Referenced SG': sg_ref.get('GroupId', ''),
                        'Used By': resources_str,
                        'Region': region
                    })
            
            # If no rules found, add a placeholder entry
            if not sg.get('IpPermissions', []) and not sg.get('IpPermissionsEgress', []):
                rule_counter += 1
                rule_id = f"R{rule_counter}"
                
                security_group_rules.append({
                    'Rule ID': rule_id,
                    'SG Name': sg_name,
                    'SG ID': sg_id,
                    'VPC': vpc_name,
                    'SG Description': description,
                    'Direction': 'N/A',
                    'Rule': 'No rules defined',
                    'Rule Description': '',
                    'Protocol': 'N/A',
                    'From Port': 'N/A',
                    'To Port': 'N/A',
                    'CIDR': '',
                    'Used By': resources_str,
                    'Region': region
                })
        
        return security_group_rules
    except Exception as e:
        print(f"Error getting security groups in region {region}: {e}")
        return []

def export_to_excel(security_group_rules, account_name):
    """
    Export security group rules data to Excel
    """
    import pandas as pd
    
    if not security_group_rules:
        print("No security group rules found to export.")
        return None
    
    # Create a DataFrame
    df = pd.DataFrame(security_group_rules)
    
    # Get current date for filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Use utils to create output filename
    filename = utils.create_export_filename(
        account_name, 
        "sg-rules", 
        "", 
        current_date
    )
    
    # Get output path
    output_path = utils.get_output_filepath(filename)
    
    # Create an Excel writer
    writer = pd.ExcelWriter(output_path, engine='openpyxl')
    
    # Write all security group rules to a single sheet
    print("Creating Security Group Rules sheet...")
    df.to_excel(writer, sheet_name='Security Group Rules', index=False)
    
    # Save the Excel file
    writer.close()
    
    print(f"Export successful. File saved to: {output_path}")
    return output_path

def main():
    """
    Main function to run the script
    """
    # Print title and get account information
    account_id, account_name = print_title()
    
    # Check dependencies
    check_dependencies()
    
    # Get all AWS regions
    print("\nGetting list of AWS regions...")
    regions = get_all_regions()
    print(f"Found {len(regions)} regions.")
    
    # Collect security group rules from all regions
    all_security_group_rules = []
    total_regions = len(regions)
    
    print("\nCollecting security group rules across all regions...")
    print("This may take some time depending on the number of regions and security groups.")
    
    for i, region in enumerate(regions, 1):
        progress = (i / total_regions) * 100
        print(f"[{progress:.1f}%] Processing region: {region} ({i}/{total_regions})")
        
        # Get security group rules from this region
        region_rules = get_security_group_rules(region)
        all_security_group_rules.extend(region_rules)
        
        print(f"  Found {len(region_rules)} security group rules in {region}")
        
        # Add a small delay to avoid throttling
        time.sleep(0.5)
    
    # Print summary
    total_rules = len(all_security_group_rules)
    print(f"\nTotal security group rules found across all regions: {total_rules}")
    
    if total_rules > 0:
        # Export to Excel
        print("\nExporting security group rules to Excel...")
        output_file = export_to_excel(all_security_group_rules, account_name)
        
        if output_file:
            print("\nScript completed successfully.")
            print(f"Output file: {output_file}")
    else:
        print("\nNo security group rules found. Nothing to export.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)
