#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Security Groups Export Script
Version: v1.0.0
Date: FEB-28-2025

Description:
This script exports security group information from all AWS regions
including group name, ID, VPC, inbound rules, outbound rules, and associated resources.
The data is exported to an Excel file with separate sheets for each region.

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

def format_security_rule(rule, direction):
    """
    Format a security group rule into a readable string
    """
    if direction == 'inbound':
        # Inbound rule
        src = rule.get('CidrIp', rule.get('CidrIpv6', ''))
        if not src:
            # Handle security group references
            if 'GroupId' in rule:
                src = f"sg:{rule['GroupId']}"
            elif 'GroupName' in rule:
                src = f"sg:{rule['GroupName']}"
            else:
                src = "Unknown"
        
        port_range = ''
        if 'FromPort' in rule and 'ToPort' in rule:
            if rule['FromPort'] == rule['ToPort']:
                port_range = str(rule['FromPort'])
            else:
                port_range = f"{rule['FromPort']}-{rule['ToPort']}"
        elif 'FromPort' in rule:
            port_range = f"{rule['FromPort']}+"
        elif 'ToPort' in rule:
            port_range = f"0-{rule['ToPort']}"
        else:
            port_range = 'All'
        
        protocol = rule.get('IpProtocol', 'All')
        if protocol == '-1':
            protocol = 'All'
        
        return f"{src} → {protocol}:{port_range}"
    else:
        # Outbound rule
        dst = rule.get('CidrIp', rule.get('CidrIpv6', ''))
        if not dst:
            # Handle security group references
            if 'GroupId' in rule:
                dst = f"sg:{rule['GroupId']}"
            elif 'GroupName' in rule:
                dst = f"sg:{rule['GroupName']}"
            else:
                dst = "Unknown"
        
        port_range = ''
        if 'FromPort' in rule and 'ToPort' in rule:
            if rule['FromPort'] == rule['ToPort']:
                port_range = str(rule['FromPort'])
            else:
                port_range = f"{rule['FromPort']}-{rule['ToPort']}"
        elif 'FromPort' in rule:
            port_range = f"{rule['FromPort']}+"
        elif 'ToPort' in rule:
            port_range = f"0-{rule['ToPort']}"
        else:
            port_range = 'All'
        
        protocol = rule.get('IpProtocol', 'All')
        if protocol == '-1':
            protocol = 'All'
        
        return f"{protocol}:{port_range} → {dst}"

def get_security_group_rules(sg):
    """
    Get formatted inbound and outbound rules for a security group
    """
    inbound_rules = []
    outbound_rules = []
    
    # Process inbound rules (IpPermissions)
    for permission in sg.get('IpPermissions', []):
        # Get protocol and port range
        protocol = permission.get('IpProtocol', 'All')
        if protocol == '-1':
            protocol = 'All'
        
        from_port = permission.get('FromPort', 'All')
        to_port = permission.get('ToPort', 'All')
        
        # Process IPv4 ranges
        for ip_range in permission.get('IpRanges', []):
            rule = ip_range.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            inbound_rules.append(format_security_rule(rule, 'inbound'))
        
        # Process IPv6 ranges
        for ip_range in permission.get('Ipv6Ranges', []):
            rule = ip_range.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            inbound_rules.append(format_security_rule(rule, 'inbound'))
        
        # Process security group references
        for user_id_group_pair in permission.get('UserIdGroupPairs', []):
            rule = user_id_group_pair.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            inbound_rules.append(format_security_rule(rule, 'inbound'))
    
    # Process outbound rules (IpPermissionsEgress)
    for permission in sg.get('IpPermissionsEgress', []):
        # Get protocol and port range
        protocol = permission.get('IpProtocol', 'All')
        if protocol == '-1':
            protocol = 'All'
        
        from_port = permission.get('FromPort', 'All')
        to_port = permission.get('ToPort', 'All')
        
        # Process IPv4 ranges
        for ip_range in permission.get('IpRanges', []):
            rule = ip_range.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            outbound_rules.append(format_security_rule(rule, 'outbound'))
        
        # Process IPv6 ranges
        for ip_range in permission.get('Ipv6Ranges', []):
            rule = ip_range.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            outbound_rules.append(format_security_rule(rule, 'outbound'))
        
        # Process security group references
        for user_id_group_pair in permission.get('UserIdGroupPairs', []):
            rule = user_id_group_pair.copy()
            rule['IpProtocol'] = protocol
            rule['FromPort'] = from_port
            rule['ToPort'] = to_port
            outbound_rules.append(format_security_rule(rule, 'outbound'))
    
    return {
        'inbound': inbound_rules,
        'outbound': outbound_rules
    }

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

def get_security_groups(region):
    """
    Get all security groups from a specific region with their rules and resources
    """
    security_groups = []
    
    try:
        # Create EC2 client for this region
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get all security groups
        response = ec2_client.describe_security_groups()
        
        for sg in response.get('SecurityGroups', []):
            # Get VPC name if available
            vpc_id = sg.get('VpcId', '')
            vpc_name = get_vpc_name(ec2_client, vpc_id) if vpc_id else "No VPC (EC2-Classic)"
            
            # Get inbound and outbound rules
            rules = get_security_group_rules(sg)
            inbound_rules = rules['inbound']
            outbound_rules = rules['outbound']
            
            # Get resources using this security group
            resources = get_security_group_resources(ec2_client, sg['GroupId'])
            
            # Create security group entry
            sg_entry = {
                'Name': sg.get('GroupName', 'Unnamed'),
                'ID': sg['GroupId'],
                'VPC': vpc_name,
                'Description': sg.get('Description', ''),
                'Inbound Rules': '; '.join(inbound_rules) if inbound_rules else 'None',
                'Outbound Rules': '; '.join(outbound_rules) if outbound_rules else 'None',
                'Used By': '; '.join(resources) if resources else 'None',
                'Region': region
            }
            
            security_groups.append(sg_entry)
        
        return security_groups
    except Exception as e:
        print(f"Error getting security groups in region {region}: {e}")
        return []

def export_to_excel(security_groups, account_name):
    """
    Export security groups data to Excel
    """
    import pandas as pd
    
    if not security_groups:
        print("No security groups found to export.")
        return None
    
    # Create a DataFrame
    df = pd.DataFrame(security_groups)
    
    # Organize by region
    regions = df['Region'].unique()
    
    # Get current date for filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create full path for output file
    output_file = output_dir / f"{account_name}-security-groups-export-{current_date}.xlsx"
    
    # Create an Excel writer
    writer = pd.ExcelWriter(output_file, engine='openpyxl')
    
    # First, create a summary sheet with all security groups
    print("Creating summary sheet with all security groups...")
    df.to_excel(writer, sheet_name='All Security Groups', index=False)
    
    # Then create a sheet for each region
    for region in regions:
        print(f"Creating sheet for region: {region}")
        region_df = df[df['Region'] == region]
        if not region_df.empty:
            # Remove the Region column as it's redundant in a region-specific sheet
            region_df = region_df.drop(columns=['Region'])
            region_df.to_excel(writer, sheet_name=region, index=False)
    
    # Save the Excel file
    writer.close()
    
    print(f"Export successful. File saved to: {output_file}")
    return output_file

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
    
    # Collect security groups from all regions
    all_security_groups = []
    total_regions = len(regions)
    
    print("\nCollecting security group information across all regions...")
    print("This may take some time depending on the number of regions and security groups.")
    
    for i, region in enumerate(regions, 1):
        progress = (i / total_regions) * 100
        print(f"[{progress:.1f}%] Processing region: {region} ({i}/{total_regions})")
        
        # Get security groups from this region
        region_groups = get_security_groups(region)
        all_security_groups.extend(region_groups)
        
        print(f"  Found {len(region_groups)} security groups in {region}")
        
        # Add a small delay to avoid throttling
        time.sleep(0.5)
    
    # Print summary
    total_groups = len(all_security_groups)
    print(f"\nTotal security groups found across all regions: {total_groups}")
    
    if total_groups > 0:
        # Export to Excel
        print("\nExporting security group information to Excel...")
        output_file = export_to_excel(all_security_groups, account_name)
        
        if output_file:
            print("\nScript completed successfully.")
            print(f"Output file: {output_file}")
    else:
        print("\nNo security groups found. Nothing to export.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)