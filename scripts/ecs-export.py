#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS ECS Resource Export Script
Version: v1.0.0
Date: MAR-05-2025

Description:
This script exports AWS ECS (Elastic Container Service) resources including clusters, 
services, tasks, and container details across all regions. The data is exported to 
an Excel spreadsheet with detailed information about ECS deployments.

Exported information includes: Cluster Name, Service Name, Task Definition, Task Family,
Task Revision, Task Status, Launch Type, Desired Task Count, Running Task Count, 
CPU Allocation, Memory Allocation, Container Name, Image Used, Port Mappings,
ELB Target Group, Network Mode, Subnet IDs, Security Groups, IAM Role, and Creation Date.
"""

import os
import sys
import boto3
import datetime
import time
from pathlib import Path
from botocore.exceptions import ClientError, EndpointConnectionError

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

def print_title():
    """
    Print the script title and header, and return account information.
    
    Returns:
        tuple: account_id, account_name
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS ECS (ELASTIC CONTAINER SERVICE) RESOURCE EXPORT")
    print("====================================================================")
    print("Version: v1.0.0                                 Date: MAR-05-2025")
    print("====================================================================")
    
    # Get account information
    account_id, account_name = get_account_info()
    
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    
    return account_id, account_name

def get_account_info():
    """
    Get the current AWS account ID and name.
    
    Returns:
        tuple: account_id, account_name
    """
    try:
        # Create a STS client
        sts_client = boto3.client('sts')
        
        # Get the account ID
        account_id = sts_client.get_caller_identity()["Account"]
        
        # Map to account name using utils
        account_name = utils.get_account_name(account_id, default=account_id)
        
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
        # Create EC2 client to get regions
        ec2_client = boto3.client('ec2')
        
        # Get all regions
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting AWS regions: {e}")
        
        # Fallback to common regions if we can't get the full list
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1',
            'sa-east-1'
        ]

def get_task_definition_details(ecs_client, task_definition_arn):
    """
    Get details for a specific task definition.
    
    Args:
        ecs_client: The boto3 ECS client
        task_definition_arn: The task definition ARN
        
    Returns:
        dict: Task definition details
    """
    try:
        response = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)
        return response['taskDefinition']
    except Exception as e:
        print(f"Error getting task definition details for {task_definition_arn}: {e}")
        return {}

def get_target_group_info(elbv2_client, target_group_arn):
    """
    Get details for a specific target group.
    
    Args:
        elbv2_client: The boto3 ELBv2 client
        target_group_arn: The target group ARN
        
    Returns:
        dict: Target group details
    """
    try:
        response = elbv2_client.describe_target_groups(TargetGroupArns=[target_group_arn])
        if response and 'TargetGroups' in response and response['TargetGroups']:
            return response['TargetGroups'][0]
        return {}
    except Exception as e:
        print(f"Error getting target group details for {target_group_arn}: {e}")
        return {}

def get_load_balancer_name(elbv2_client, load_balancer_arn):
    """
    Get the name of a load balancer from its ARN.
    
    Args:
        elbv2_client: The boto3 ELBv2 client
        load_balancer_arn: The load balancer ARN
        
    Returns:
        str: The load balancer name
    """
    try:
        response = elbv2_client.describe_load_balancers(LoadBalancerArns=[load_balancer_arn])
        if response and 'LoadBalancers' in response and response['LoadBalancers']:
            return response['LoadBalancers'][0].get('LoadBalancerName', 'Unknown')
        return 'Unknown'
    except Exception as e:
        print(f"Error getting load balancer name for {load_balancer_arn}: {e}")
        return 'Unknown'

def get_ecs_resources(region):
    """
    Collect ECS resource information for a specific region.
    
    Args:
        region: AWS region name
        
    Returns:
        list: List of dictionaries with ECS resource information
    """
    print(f"\nCollecting ECS information in region: {region}")
    ecs_resources = []
    
    try:
        # Create ECS, ELBv2, and EC2 clients for this region
        ecs_client = boto3.client('ecs', region_name=region)
        elbv2_client = boto3.client('elbv2', region_name=region)
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get all ECS clusters
        cluster_arns = []
        paginator = ecs_client.get_paginator('list_clusters')
        for page in paginator.paginate():
            cluster_arns.extend(page['clusterArns'])
        
        if not cluster_arns:
            print(f"  No ECS clusters found in {region}")
            return []
        
        print(f"  Found {len(cluster_arns)} ECS clusters")
        
        # Get details for each cluster
        for i, cluster_arn in enumerate(cluster_arns, 1):
            print(f"  Processing cluster {i}/{len(cluster_arns)}: {cluster_arn.split('/')[-1]}")
            
            try:
                # Get cluster details
                cluster_response = ecs_client.describe_clusters(
                    clusters=[cluster_arn],
                    include=['SETTINGS', 'CONFIGURATIONS', 'TAGS']
                )
                
                if not cluster_response['clusters']:
                    continue
                    
                cluster = cluster_response['clusters'][0]
                cluster_name = cluster['clusterName']
                
                # Get all services in this cluster
                service_arns = []
                services_paginator = ecs_client.get_paginator('list_services')
                for page in services_paginator.paginate(cluster=cluster_arn):
                    service_arns.extend(page['serviceArns'])
                
                if not service_arns:
                    print(f"    No services found in cluster {cluster_name}")
                    continue
                
                print(f"    Found {len(service_arns)} services in cluster {cluster_name}")
                
                # Process services in batches (describe_services has a limit of 10 services per call)
                for j in range(0, len(service_arns), 10):
                    service_batch = service_arns[j:j+10]
                    
                    # Get service details
                    service_response = ecs_client.describe_services(
                        cluster=cluster_arn,
                        services=service_batch,
                        include=['TAGS']
                    )
                    
                    for service in service_response['services']:
                        service_name = service['serviceName']
                        print(f"      Processing service: {service_name}")
                        
                        # Get task definition details
                        task_definition_arn = service['taskDefinition']
                        task_def = get_task_definition_details(ecs_client, task_definition_arn)
                        
                        task_family = task_def.get('family', 'Unknown')
                        task_revision = task_def.get('revision', 'Unknown')
                        cpu_allocation = task_def.get('cpu', 'Unknown')
                        memory_allocation = task_def.get('memory', 'Unknown')
                        network_mode = task_def.get('networkMode', 'Unknown')
                        
                        # Get the IAM role
                        execution_role_arn = task_def.get('executionRoleArn', 'None')
                        task_role_arn = task_def.get('taskRoleArn', 'None')
                        
                        # Extract role name from ARN
                        execution_role_name = execution_role_arn.split('/')[-1] if execution_role_arn != 'None' else 'None'
                        task_role_name = task_role_arn.split('/')[-1] if task_role_arn != 'None' else 'None'
                        
                        # Format roles
                        iam_roles = []
                        if execution_role_name != 'None':
                            iam_roles.append(f"Execution: {execution_role_name}")
                        if task_role_name != 'None':
                            iam_roles.append(f"Task: {task_role_name}")
                        
                        iam_role = ", ".join(iam_roles) if iam_roles else "None"
                        
                        # Get launch type
                        launch_type = ''
                        if 'launchType' in service:
                            launch_type = service['launchType']
                        elif 'capacityProviderStrategy' in service and service['capacityProviderStrategy']:
                            provider = service['capacityProviderStrategy'][0]['capacityProvider']
                            if 'FARGATE' in provider:
                                launch_type = 'FARGATE'
                            else:
                                launch_type = f"CapacityProvider: {provider}"
                        else:
                            launch_type = 'Unknown'
                        
                        # Get desired and running count
                        desired_count = service.get('desiredCount', 0)
                        running_count = service.get('runningCount', 0)
                        
                        # Get creation time
                        created_at = service.get('createdAt', datetime.datetime.now())
                        if isinstance(created_at, datetime.datetime):
                            created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
                            
                        # Get load balancer info if available
                        elb_target_groups = []
                        if 'loadBalancers' in service and service['loadBalancers']:
                            for lb in service['loadBalancers']:
                                if 'targetGroupArn' in lb:
                                    target_group_arn = lb['targetGroupArn']
                                    target_group = get_target_group_info(elbv2_client, target_group_arn)
                                    
                                    if target_group and 'TargetGroupName' in target_group and 'LoadBalancerArns' in target_group and target_group['LoadBalancerArns']:
                                        lb_name = get_load_balancer_name(elbv2_client, target_group['LoadBalancerArns'][0])
                                        elb_target_groups.append(f"{lb_name}:{target_group['TargetGroupName']}")
                                    else:
                                        elb_target_groups.append(target_group_arn.split('/')[-1] if target_group_arn else 'Unknown')
                        
                        elb_target_group = ', '.join(elb_target_groups) if elb_target_groups else 'None'
                        
                        # Get network configuration if available
                        subnet_ids = []
                        security_groups = []
                        
                        if 'networkConfiguration' in service and 'awsvpcConfiguration' in service['networkConfiguration']:
                            vpc_config = service['networkConfiguration']['awsvpcConfiguration']
                            subnet_ids = vpc_config.get('subnets', [])
                            security_groups = vpc_config.get('securityGroups', [])
                        
                        # Get tasks for this service to get task status
                        task_arns = []
                        tasks_paginator = ecs_client.get_paginator('list_tasks')
                        for page in tasks_paginator.paginate(cluster=cluster_arn, serviceName=service_name):
                            task_arns.extend(page['taskArns'])
                        
                        # If there are no tasks, we still want to show the service
                        if not task_arns:
                            # Create a base entry for the service with no running tasks
                            base_entry = {
                                'Cluster Name': cluster_name,
                                'Service Name': service_name,
                                'Task Definition': task_definition_arn.split('/')[-1],
                                'Task Family': task_family,
                                'Task Revision': task_revision,
                                'Task Status': 'No Running Tasks',
                                'Launch Type': launch_type,
                                'Desired Task Count': desired_count,
                                'Running Task Count': running_count,
                                'CPU Allocation': cpu_allocation,
                                'Memory Allocation': memory_allocation,
                                'Container Name': 'N/A',
                                'Image Used': 'N/A',
                                'Port Mappings': 'N/A',
                                'ELB Target Group': elb_target_group,
                                'Network Mode': network_mode,
                                'Subnet IDs': ', '.join(subnet_ids) if subnet_ids else 'None',
                                'Security Groups': ', '.join(security_groups) if security_groups else 'None',
                                'IAM Role': iam_role,
                                'Created At': created_at
                            }
                            ecs_resources.append(base_entry)
                            continue
                        
                        # Get details for each task
                        for k in range(0, len(task_arns), 100):  # describe_tasks has a limit of 100 tasks per call
                            task_batch = task_arns[k:k+100]
                            
                            task_response = ecs_client.describe_tasks(
                                cluster=cluster_arn,
                                tasks=task_batch
                            )
                            
                            for task in task_response['tasks']:
                                task_status = task.get('lastStatus', 'Unknown')
                                
                                # Process each container in the task
                                for container in task.get('containers', []):
                                    container_name = container.get('name', 'Unknown')
                                    container_image = container.get('image', 'Unknown')
                                    
                                    # Get container definition for port mappings
                                    container_def = None
                                    for c in task_def.get('containerDefinitions', []):
                                        if c.get('name') == container_name:
                                            container_def = c
                                            break
                                    
                                    # Extract port mappings
                                    port_mappings = []
                                    if container_def and 'portMappings' in container_def and container_def['portMappings']:
                                        for pm in container_def['portMappings']:
                                            host_port = pm.get('hostPort', 'Auto')
                                            container_port = pm.get('containerPort', 'Unknown')
                                            protocol = pm.get('protocol', 'tcp')
                                            
                                            port_mappings.append(f"{container_port}:{host_port}/{protocol}")
                                    
                                    # Create entry for this container
                                    ecs_resources.append({
                                        'Cluster Name': cluster_name,
                                        'Service Name': service_name,
                                        'Task Definition': task_definition_arn.split('/')[-1],
                                        'Task Family': task_family,
                                        'Task Revision': task_revision,
                                        'Task Status': task_status,
                                        'Launch Type': task.get('launchType', launch_type),
                                        'Desired Task Count': desired_count,
                                        'Running Task Count': running_count,
                                        'CPU Allocation': cpu_allocation,
                                        'Memory Allocation': memory_allocation,
                                        'Container Name': container_name,
                                        'Image Used': container_image,
                                        'Port Mappings': ', '.join(port_mappings) if port_mappings else 'None',
                                        'ELB Target Group': elb_target_group,
                                        'Network Mode': network_mode,
                                        'Subnet IDs': ', '.join(subnet_ids) if subnet_ids else 'None',
                                        'Security Groups': ', '.join(security_groups) if security_groups else 'None',
                                        'IAM Role': iam_role,
                                        'Created At': created_at
                                    })
                
            except Exception as e:
                print(f"    Error processing cluster {cluster_arn}: {e}")
                continue
                
    except EndpointConnectionError:
        print(f"  ECS service is not available in region {region}")
    except Exception as e:
        print(f"  Error collecting ECS data in region {region}: {e}")
    
    return ecs_resources

def main():
    """
    Main function to coordinate the ECS export process.
    """
    try:
        # Print the script title and get account information
        account_id, account_name = print_title()
        
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Import pandas after checking dependencies
        import pandas as pd
        
        # Ask user if they want to scan all regions or a specific region
        print("\nWould you like to scan all regions or a specific region?")
        region_choice = input("Enter 'all' or a specific region (e.g., us-east-1): ").strip().lower()
        
        # Get regions to scan
        all_regions = get_all_regions()
        
        if region_choice == 'all':
            regions_to_scan = all_regions
        else:
            # Validate region choice
            if region_choice in all_regions:
                regions_to_scan = [region_choice]
            else:
                print(f"Invalid region: {region_choice}. Using default region us-east-1.")
                regions_to_scan = ['us-east-1']
        
        print(f"\nScanning {len(regions_to_scan)} AWS regions for ECS resources...")
        
        # Collect ECS information from all regions
        all_ecs_resources = []
        for region in regions_to_scan:
            region_resources = get_ecs_resources(region)
            all_ecs_resources.extend(region_resources)
            # Add a small delay to avoid throttling
            time.sleep(0.5)
        
        if not all_ecs_resources:
            print("\nNo ECS resources found in the scanned regions.")
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_ecs_resources)
        
        # Generate filename with current date
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")
        
        # Specify region in filename if a specific region was chosen
        region_suffix = "" if region_choice == 'all' else f"-{region_choice}"
        
        # Create export filename using utils
        filename = utils.create_export_filename(
            account_name, 
            "ecs-resources", 
            region_suffix, 
            current_date
        )
        
        # Export to Excel
        output_path = utils.save_dataframe_to_excel(df, filename)
        
        if output_path:
            print(f"\nExport completed successfully!")
            print(f"File saved as: {output_path}")
            print(f"Total ECS resources collected: {len(all_ecs_resources)}")
        else:
            print("\nError exporting data to Excel.")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
