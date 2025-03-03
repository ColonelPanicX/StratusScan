#!/usr/bin/env python3
# StratusScan.py - Main menu script for AWS resource export tools

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: StratusScan - AWS Resource Exporter Main Menu
Version: v1.3.0
Date: FEB-28-2025

Description:
This script provides a centralized interface for executing various AWS resource
export tools within the StratusScan package. It allows users to select which resource 
type to export (EC2 instances, VPC resources, etc.) and calls the appropriate script 
to perform the selected operation.

Deployment Structure:
- The main menu script should be located in the root directory of the StratusScan package
- Individual export scripts should be located in the 'scripts' subdirectory
- Exported files will be saved to the 'output' subdirectory
- Account mappings and configuration are stored in config.json
"""

import os
import sys
import subprocess
import zipfile
import datetime
from pathlib import Path

# Add the current directory to the path to ensure we can import utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the utility module
try:
    import utils
except ImportError:
    print("ERROR: Could not import the utils module. Make sure utils.py is in the same directory as this script.")
    sys.exit(1)

def clear_screen():
    """
    Clear the terminal screen based on the operating system.
    """
    # Check if we're on Windows or Unix/Linux/MacOS
    if os.name == 'nt':  # Windows
        os.system('cls')
    else:  # Unix/Linux/MacOS
        os.system('clear')

def print_header():
    """
    Print the main menu header with version information.
    """
    clear_screen()
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("                         STRATUSSCAN                                ")
    print("                  AWS RESOURCE EXPORTER MENU                        ")
    print("====================================================================")
    print("Version: v1.3.0                                 Date: FEB-28-2025")
    print("====================================================================")
    
    # Get the current AWS account ID and map to account name
    try:
        # Create a boto3 STS client
        import boto3
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()["Account"]
        account_name = utils.get_account_name(account_id, default=account_id)
        
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print(f"Error getting account information: {e}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    print("====================================================================")
    return account_id, account_name

def check_dependency(dependency):
    """
    Check if a Python dependency is installed.
    
    Args:
        dependency: Name of the Python package to check
        
    Returns:
        bool: True if installed, False otherwise
    """
    try:
        __import__(dependency)
        return True
    except ImportError:
        return False

def install_dependency(dependency):
    """
    Install a Python dependency after user confirmation.
    
    Args:
        dependency: Name of the Python package to install
        
    Returns:
        bool: True if installed successfully, False otherwise
    """
    print(f"\nPackage '{dependency}' is required but not installed.")
    response = input(f"Would you like to install {dependency}? (y/n): ").lower()
    
    if response == 'y':
        try:
            import subprocess
            print(f"Installing {dependency}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dependency])
            print(f"✓ Successfully installed {dependency}")
            return True
        except Exception as e:
            print(f"Error installing {dependency}: {e}")
            return False
    else:
        print(f"Cannot proceed without {dependency}.")
        return False

def check_dependencies():
    """
    Check and install common required dependencies.
    
    Returns:
        bool: True if all dependencies are satisfied, False otherwise
    """
    print("Checking required dependencies...")
    required_packages = ['boto3', 'pandas', 'openpyxl']
    
    for package in required_packages:
        if check_dependency(package):
            print(f"✓ {package} is already installed")
        else:
            if not install_dependency(package):
                return False
    
    return True

def ensure_directory_structure():
    """
    Ensure the required directory structure exists.
    Creates the scripts and output directories if they don't exist.
    """
    # Get the base directory (where this script is located)
    base_dir = Path(__file__).parent.absolute()
    
    # Create scripts directory if it doesn't exist
    scripts_dir = base_dir / "scripts"
    if not scripts_dir.exists():
        print(f"Creating scripts directory: {scripts_dir}")
        scripts_dir.mkdir(exist_ok=True)
    
    # Create output directory if it doesn't exist
    output_dir = base_dir / "output"
    if not output_dir.exists():
        print(f"Creating output directory: {output_dir}")
        output_dir.mkdir(exist_ok=True)
    
    # Check if config.json exists, create from template if it doesn't
    config_path = base_dir / "config.json"
    config_template_path = base_dir / "config-template.json"
    
    if not config_path.exists() and config_template_path.exists():
        print(f"No configuration file found. Creating default config.json from template.")
        try:
            import shutil
            shutil.copy(config_template_path, config_path)
            print(f"Created default config.json. You may want to edit this file to add your account mappings.")
        except Exception as e:
            print(f"Warning: Could not create config.json: {e}")
    
    return scripts_dir, output_dir

def get_script_mapping():
    """
    Create a direct mapping of menu options to script files.
    
    Returns:
        dict: Dictionary mapping menu options to script paths
    """
    scripts_dir, _ = ensure_directory_structure()
    
    # Define the direct mapping for the menu (in alphabetical order)
    script_mapping = {
        "1": {
            "name": "Billing",
            "file": scripts_dir / "billing-export.py",
            "description": "Export AWS billing data"
        },
        "2": {
            "name": "Cost Optimization",
            "file": scripts_dir / "trusted-advisor-cost-optimization-export.py",
            "description": "Export Trusted Advisor cost optimization recommendations"
        },
        "3": {
            "name": "EBS (Elastic Block Storage)",
            "file": scripts_dir / "ebs-export.py",
            "description": "Export EBS volume information"
        },
        "4": {
            "name": "EC2",
            "file": scripts_dir / "ec2-export.py",
            "description": "Export EC2 instance data"
        },
        "5": {
            "name": "ELB (Elastic Load Balancer)",
            "file": scripts_dir / "elb-export.py",
            "description": "Export load balancer information"
        },
        "6": {
            "name": "RDS (Relational Database Service)",
            "file": scripts_dir / "rds-instance-export.py",
            "description": "Export RDS instance information"
        },
        "7": {
            "name": "S3",
            "file": scripts_dir / "s3-export.py",
            "description": "Export S3 bucket information"
        },
        "8": {
            "name": "Security Groups",
            "file": scripts_dir / "security-groups-export.py",
            "description": "Export security group information"
        },
        "9": {
            "name": "VPC/Subnet",
            "file": scripts_dir / "vpc-data-export.py",
            "description": "Export VPC and subnet information"
        },
        "10": {
            "name": "Create Output Archive",
            "file": None,  # Special case, handled directly
            "description": "Zip all exports to a single file"
        }
    }
    
    # Verify the script files exist (only for actual scripts)
    for option, script_info in script_mapping.items():
        if script_info["file"] is not None and not script_info["file"].exists():
            print(f"Warning: Script file {script_info['file']} for option {option} ({script_info['name']}) not found!")
    
    return script_mapping

def execute_script(script_path):
    """
    Execute the selected export script.
    
    Args:
        script_path: Path to the script to execute
    """
    try:
        # Clear the screen before executing the script
        clear_screen()
        
        print(f"Executing: {script_path}")
        print("=" * 60)
        
        # Execute the script as a subprocess
        result = subprocess.run([sys.executable, str(script_path)], 
                              check=True)
        
        if result.returncode == 0:
            print("\nScript execution completed successfully.")
        else:
            print(f"\nScript execution failed with return code: {result.returncode}")
    
    except subprocess.CalledProcessError as e:
        print(f"Error executing script: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def create_output_archive(account_name):
    """
    Create a zip archive of the output directory.
    
    Args:
        account_name: The AWS account name to use in the filename
        
    Returns:
        bool: True if archive was created successfully, False otherwise
    """
    try:
        # Clear the screen
        clear_screen()
        
        print("====================================================================")
        print("CREATING OUTPUT ARCHIVE")
        print("====================================================================")
        
        # Get the output directory path
        output_dir = Path(__file__).parent / "output"
        
        # Check if output directory exists and has files
        if not output_dir.exists():
            print(f"Output directory not found: {output_dir}")
            return False
        
        files = list(output_dir.glob("*.*"))
        if not files:
            print("No files found in the output directory to archive.")
            return False
        
        print(f"Found {len(files)} files to archive.")
        
        # Create filename with current date
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")
        zip_filename = f"{account_name}-output-export-{current_date}.zip"
        zip_path = Path(__file__).parent / zip_filename
        
        # Create the zip file
        print(f"Creating archive: {zip_filename}")
        print("Please wait...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                # Archive file with relative path inside the zip
                zipf.write(file, arcname=file.name)
                print(f"  Added: {file.name}")
        
        print("\nArchive creation completed successfully!")
        print(f"Archive saved to: {zip_path}")
        
        return True
    
    except Exception as e:
        print(f"Error creating archive: {e}")
        return False

def display_menu():
    """
    Display the main menu and handle user selection.
    """
    try:
        # Print header and get account information
        account_id, account_name = print_header()
        
        # Check dependencies
        if not check_dependencies():
            print("Required dependencies are missing. Please install them to continue.")
            sys.exit(1)
        
        # Ensure directory structure
        ensure_directory_structure()
        
        # Get script mapping
        script_mapping = get_script_mapping()
        
        if not script_mapping:
            print("\nNo scripts found in the mapping. Please ensure script files exist in the scripts directory.")
            sys.exit(1)
        
        # Display menu options
        print("\nAvailable export tools:")
        for option, script_info in script_mapping.items():
            print(f"{option}. {script_info['name']} - {script_info['description']}")
        
        # Display exit option
        exit_option = str(len(script_mapping) + 1)
        print(f"{exit_option}. Exit")
        
        # Get user selection
        while True:
            print("\nSelect an export tool to run:")
            user_choice = input("Enter your choice: ")
            
            if user_choice == exit_option:
                clear_screen()
                print("Exiting StratusScan. Thank you for using the tool.")
                break
            
            elif user_choice in script_mapping:
                selected_script = script_mapping[user_choice]
                print(f"\nYou selected: {selected_script['name']} - {selected_script['description']}")
                
                # Confirm execution
                confirm = input("Do you want to continue? (y/n): ").lower()
                if confirm == 'y':
                    # Handle special case for creating output archive
                    if user_choice == "10":  # Create Output Archive
                        success = create_output_archive(account_name)
                    else:
                        # Normal script execution
                        execute_script(selected_script['file'])
                    
                    # Ask if user wants to run another tool
                    another = input("\nWould you like to run another export tool? (y/n): ").lower()
                    if another != 'y':
                        clear_screen()
                        print("Exiting StratusScan. Thank you for using the tool.")
                        break
                    else:
                        # Return to the main menu (refresh display)
                        account_id, account_name = print_header()
                        # Re-display the menu options
                        print("\nAvailable export tools:")
                        for option, script_info in script_mapping.items():
                            print(f"{option}. {script_info['name']} - {script_info['description']}")
                        print(f"{exit_option}. Exit")
                
            else:
                print("Invalid selection. Please try again.")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def main():
    """
    Main function to display the menu and handle script execution.
    """
    try:
        display_menu()
    except Exception as e:
        print(f"Error in main function: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
