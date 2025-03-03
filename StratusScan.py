#!/usr/bin/env python3
# StratusScan.py - Main menu script for AWS resource export tools

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: StratusScan - AWS Resource Exporter Main Menu
Version: v1.3.3
Date: MAR-03-2025

Description:
This script provides a centralized interface for executing various AWS resource
export tools within the StratusScan package. It allows users to select which resource 
type to export (EC2 instances, VPC resources, S3 buckets, etc.) and calls the appropriate script 
to perform the selected operation.

Deployment Structure:
- The main menu script should be located in the root directory of the StratusScan package
- Individual export scripts should be located in the 'scripts' subdirectory
- Exported files will be saved to the 'output' subdirectory
- Account mappings and configuration are stored in config.json
"""

import os
import sys
import importlib.util
import subprocess
import json
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

# Script metadata
VERSION = "v1.3.3"
RELEASE_DATE = "MAR-03-2025"

def print_header():
    """
    Print the main menu header with version information.
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("                         STRATUSSCAN                                ")
    print("                  AWS RESOURCE EXPORTER MENU                        ")
    print("====================================================================")
    print(f"Version: {VERSION}                          Date: {RELEASE_DATE}")
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

def find_scripts(scripts_dir):
    """
    Find all AWS export scripts in the scripts subdirectory.
    
    Args:
        scripts_dir: Path to the scripts directory
        
    Returns:
        list: List of script file paths
    """
    # Look for Python files in the scripts directory
    script_files = list(scripts_dir.glob("*.py"))
    
    if not script_files:
        print("No export scripts found in the scripts directory.")
        print("Please add some scripts to the scripts directory and try again.")
    
    return script_files

def extract_script_metadata(script_file):
    """
    Extract metadata from a script file.
    
    Args:
        script_file: Path to the script file
        
    Returns:
        dict: Dictionary containing script metadata
    """
    try:
        # Read the script file to extract metadata
        with open(script_file, 'r') as f:
            content = f.read()
            
            # Extract title from the script
            title = None
            title_match = content.find("Title:")
            if title_match >= 0:
                title_line = content[title_match:].split('\n')[0]
                title = title_line.replace("Title:", "").strip()
            
            # If no title found, use the filename
            if not title:
                title = script_file.stem.replace("-", " ").replace("_", " ").title()
            
            # Extract version from the script
            version = "Unknown"
            version_match = content.find("Version:")
            if version_match >= 0:
                version_line = content[version_match:].split('\n')[0]
                version = version_line.replace("Version:", "").strip()
            
            # Extract description
            description = "No description available"
            desc_match = content.find("Description:")
            if desc_match >= 0:
                desc_text = content[desc_match:].split('\n\n')[0]
                desc_lines = desc_text.replace("Description:", "").strip().split('\n')
                description = ' '.join([line.strip() for line in desc_lines])
                if len(description) > 100:
                    description = description[:97] + "..."
            
            # Create metadata dictionary
            return {
                'filename': script_file.name,
                'path': script_file,
                'title': title,
                'version': version,
                'description': description
            }
    except Exception as e:
        print(f"Warning: Could not process {script_file.name}: {e}")
        return {
            'filename': script_file.name,
            'path': script_file,
            'title': script_file.stem.replace("-", " ").replace("_", " ").title(),
            'version': "Unknown",
            'description': "Could not extract description"
        }

def list_available_scripts(scripts_dir):
    """
    List all available AWS export scripts in the scripts subdirectory.
    
    Args:
        scripts_dir: Path to the scripts directory
        
    Returns:
        dict: Dictionary mapping menu options to script information
    """
    print(f"Scanning for export scripts in: {scripts_dir}")
    
    # Find all Python files in the scripts directory
    script_files = find_scripts(scripts_dir)
    
    # Create a dictionary to map menu options to script info
    script_options = {}
    option_num = 1
    
    print("\nAvailable export tools:")
    
    if not script_files:
        return script_options
    
    for script_file in sorted(script_files):
        # Extract metadata from the script file
        metadata = extract_script_metadata(script_file)
        
        # Add to the dictionary
        script_options[str(option_num)] = metadata
        
        # Print the menu option
        print(f"{option_num}. {metadata['title']} ({metadata['version']})")
        print(f"   {metadata['description']}")
        option_num += 1
    
    return script_options

def execute_script(script_path):
    """
    Execute the selected export script.
    
    Args:
        script_path: Path to the script to execute
    """
    try:
        print(f"\nExecuting: {script_path}")
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
    except KeyboardInterrupt:
        print("\nScript execution cancelled by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")

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
        scripts_dir, output_dir = ensure_directory_structure()
        
        # List available scripts
        script_options = list_available_scripts(scripts_dir)
        
        if not script_options:
            print("\nNo export scripts found. Please add scripts to the 'scripts' directory.")
            sys.exit(1)
        
        # Display exit option
        exit_option = str(len(script_options) + 1)
        print(f"{exit_option}. Exit")
        
        # Get user selection
        while True:
            print("\nSelect an export tool to run:")
            user_choice = input("Enter your choice: ")
            
            if user_choice == exit_option:
                print("Exiting StratusScan. Thank you for using the tool.")
                break
            
            elif user_choice in script_options:
                selected_script = script_options[user_choice]
                print(f"\nYou selected: {selected_script['title']} ({selected_script['version']})")
                
                # Confirm execution
                confirm = input("Do you want to continue? (y/n): ").lower()
                if confirm == 'y':
                    execute_script(selected_script['path'])
                    
                    # Ask if user wants to run another tool
                    another = input("\nWould you like to run another export tool? (y/n): ").lower()
                    if another != 'y':
                        print("Exiting StratusScan. Thank you for using the tool.")
                        break
                
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
        # Display the version information and menu
        display_menu()
    except Exception as e:
        print(f"Error in main function: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
