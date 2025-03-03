# StratusScan - AWS Resource Exporter

StratusScan is a collection of Python scripts designed to scan and export AWS resource information across multiple accounts and regions. It provides a unified interface for gathering detailed information about various AWS resources and exporting the data into standardized Excel spreadsheets.

## Features

- **Centralized Menu Interface**: Easy-to-use menu for executing various export tools
- **Multi-Region Support**: Scan resources across a specific region or all regions
- **Account Mapping**: Translate AWS account IDs to friendly names
- **Consistent Output**: Standardized Excel exports with timestamp-based filenames
- **Export Archive**: Built-in functionality to zip all exports into a single file
- **Dependency Management**: Automatic checking and installation of required Python packages

## Supported AWS Resources

StratusScan can export information about the following AWS resources:

- **Billing**: Monthly or yearly AWS billing data by service
- **Cost Optimization**: Trusted Advisor cost optimization recommendations
- **EBS Volumes**: Volume IDs, size, state, and attachment information
- **EC2 Instances**: Detailed instance information including OS, size, and network config
- **Elastic Load Balancers**: Classic, Application, and Network load balancers
- **RDS Instances**: Database engine, size, storage, and connection information
- **S3 Buckets**: Bucket information including size, object count, and region
- **Security Groups**: Group details, inbound/outbound rules, and resource associations
- **VPC Resources**: VPCs, subnets, NAT gateways, peering connections, and Elastic IPs

## Requirements

- Python 3.6+
- AWS credentials configured (via AWS CLI, environment variables, or instance profile)
- Required Python packages:
  - boto3
  - pandas
  - openpyxl

## Installation

1. Clone or download the StratusScan repository
2. Ensure Python 3.6+ is installed
3. Install the required Python packages:
   ```
   pip install boto3 pandas openpyxl
   ```
4. Set up your AWS credentials using one of the [standard AWS methods](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)

## Directory Structure

The repository is organized as follows:

```
StratusScan/
├── StratusScan.py      (Main menu script)
├── utils.py            (Shared utilities)
├── config.json         (Configuration file)
├── scripts/            (Directory for all export scripts)
│   ├── billing-export.py
│   ├── trusted-advisor-cost-optimization-export.py
│   ├── ebs-export.py
│   ├── ec2-export.py
│   ├── elb-export.py
│   ├── rds-instance-export.py
│   ├── s3-export.py
│   ├── security-groups-export.py
│   └── vpc-data-export.py
└── output/             (Directory for all exported files)
    └── ... (Export files will be saved here)
```

## Configuration

StratusScan uses a configuration file (`config.json`) to store account mappings and other settings. A template is provided as `config-template.json`. Copy this file to `config.json` and customize it:

```json
{
  "account_mappings": {
    "123456789012": "PROD",
    "234567890123": "DEV",
    "345678901234": "TEST"
  },
  "agency_name": "YOUR-ORGANIZATION",
  "default_regions": ["us-east-1", "us-west-2"],
  "resource_preferences": {
    "ec2": {
      "default_filter": "all", 
      "include_stopped": true,
      "default_region": "all"
    },
    "vpc": {
      "default_export_type": "all",
      "default_region": "all"
    }
  }
}
```

## Usage

1. Run the main menu script:
   ```
   python StratusScan.py
   ```

2. Select the resource type you want to export from the menu

3. Follow the prompts to configure the export (region, filters, etc.)

4. Find the exported file in the `output` directory

5. Optionally, use the "Create Output Archive" option to zip all exports

## Individual Export Scripts

While the main menu is the recommended way to run the export tools, you can also run individual scripts directly:

```
python scripts/ec2-export.py
```

Each script will prompt for any required information and save its output to the `output` directory.

## AWS Permissions

The scripts require read-only access to the AWS resources they're exporting. At a minimum, you'll need the following AWS permission policies:

- ReadOnlyAccess
- For billing data: ViewBilling
- For Trusted Advisor: AWSSupportAccess (requires Business or Enterprise Support plan)

For specific resource types, more limited permissions can be used. Refer to the AWS documentation for the specific services.

## Troubleshooting

- **Missing Dependencies**: If you see errors about missing Python packages, run `pip install -r requirements.txt` or let the script install them automatically when prompted.
- **AWS Credentials**: Ensure your AWS credentials are properly configured and have the necessary permissions.
- **Rate Limiting**: If you hit AWS API rate limits, try scanning fewer regions at once