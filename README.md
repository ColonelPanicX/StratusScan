# StratusScan - AWS Resource Exporter

> **Important**: It is recommended to run the `configure.py` script before running the main script to set up your configuration, but it is not necessary.

StratusScan is a collection of Python scripts designed to scan and export AWS resource information across multiple accounts and regions. This version is optimized for AWS Commercial environments and provides a unified interface for gathering detailed information about various AWS resources and exporting the data into standardized Excel spreadsheets.

## Features

- **Centralized Menu Interface**: Easy-to-use menu for executing various export tools
- **Multi-Region Support**: Scan resources across specific regions or all AWS commercial regions
- **Account Mapping**: Translate AWS account IDs to friendly organization names
- **Consistent Output**: Standardized Excel exports with timestamp-based filenames
- **Export Archive**: Built-in functionality to zip all exports into a single file
- **Dependency Management**: Automatic checking and installation of required Python packages
- **Full Service Availability**: Access to all AWS commercial services including Trusted Advisor and Compute Optimizer

## Supported AWS Resources

StratusScan can export information about the following AWS resources:

- **EBS Volumes**: Volume IDs, size, state, and attachment information
- **EBS Snapshots**: Snapshot IDs, size, encryption status, and creation dates
- **EC2 Instances**: Detailed instance information including OS, size, and network config
- **EKS Clusters**: Kubernetes cluster information, node groups, and configurations
- **Elastic Load Balancers**: Classic, Application, and Network load balancers
- **IAM Comprehensive**: Complete IAM analysis including users, roles, policies, and permissions
- **IAM Basic**: Basic IAM user and role information
- **IAM Identity Center**: AWS SSO/Identity Center users and assignments
- **IAM Identity Center Groups**: Identity Center group memberships and assignments
- **IAM Identity Center Comprehensive**: Complete Identity Center analysis with users, groups, permission sets, and assignments
- **IAM Policies**: Detailed policy analysis including managed and inline policies
- **IAM Roles**: Role details, trust policies, and attached permissions
- **Network ACLs**: NACL rules, subnet associations, and configurations
- **Organizations**: AWS Organizations structure, accounts, and organizational units
- **RDS Instances**: Database engine, size, storage, and connection information
- **S3 Buckets**: Bucket information including size, object count, and region
- **Security Groups**: Group details, inbound/outbound rules, and resource associations
- **Security Hub**: Security findings, compliance status, and remediation guidance
- **Services in Use**: Analysis of AWS services currently being used in your environment
- **VPC Resources**: VPCs, subnets, NAT gateways, peering connections, and Elastic IPs
- **All-in-One Reports**: Comprehensive resource exports by category (Storage, Compute, Network)

## Requirements

- Python 3.6+
- AWS credentials configured (via AWS CLI, environment variables, or instance profile)
- Access to AWS Commercial environment
- Required Python packages:
  - boto3
  - pandas
  - openpyxl

## Installation

1. Clone or download the StratusScan repository
2. Ensure Python 3.6+ is installed
3. While the scripts will check for missing dependencies and prompt to have them installed, you can preemptively install the required packages by running the following command:
   ```
   pip install boto3 pandas openpyxl
   ```
4. Set up your AWS credentials using one of the [standard AWS methods](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)

## AWS Authentication

To authenticate with AWS, ensure your credentials are configured:

### Using AWS CLI
```bash
aws configure
AWS Access Key ID: [Your AWS Access Key]
AWS Secret Access Key: [Your AWS Secret Key]
Default region name: us-east-1
Default output format: json
```

### Using Environment Variables
```bash
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Using Instance Profile
If running on an EC2 instance, the instance profile will automatically provide credentials.

## Directory Structure

The repository is organized as follows:

```
StratusScan/
├── stratusscan.py                                   (Main menu script)
├── configure.py                                     (Configuration setup script)
├── utils.py                                         (Utility functions)
├── config.json                                      (Configuration file)
├── scripts/                                         (Directory for all export scripts)
│   ├── compute-resources.py                         (All compute resources in one report)
│   ├── ebs-snapshots.py
│   ├── ebs-volumes.py
│   ├── ec2-export.py
│   ├── eks-export.py
│   ├── elb-export.py
│   ├── iam-comprehensive-export.py
│   ├── iam-export.py
│   ├── iam-identity-center-comprehensive-export.py
│   ├── iam-identity-center-export.py
│   ├── iam-identity-center-groups-export.py
│   ├── iam-identity-center-permission-sets-export.py
│   ├── iam-policies-export.py
│   ├── iam-roles-export.py
│   ├── nacl-export.py
│   ├── network-resources.py                         (All network resources in one report)
│   ├── organizations-export.py
│   ├── rds-export.py
│   ├── s3-export.py
│   ├── security-groups-export.py
│   ├── security-hub-export.py
│   ├── services-in-use-export.py
│   ├── storage-resources.py                         (All storage resources in one report)
│   └── vpc-data-export.py
└── output/                                          (Directory for all exported files)
    └── ... (Export files will be saved here)
```

## Configuration

StratusScan uses a configuration file (`config.json`) to store account mappings and AWS-specific settings. You can either:

1. **Recommended**: Run the configuration setup script first:
   ```
   python configure.py
   ```
   This interactive script will help you set up your configuration properly.

2. **Manual**: Create and customize the configuration file manually using the template below:

```json
{
  "account_mappings": {
    "123456789012": "PROD-ACCOUNT",
    "234567890123": "DEV-ACCOUNT",
    "345678901234": "TEST-ACCOUNT"
  },
  "organization_name": "YOUR-ORGANIZATION",
  "default_regions": ["us-east-1", "us-west-2"],
  "resource_preferences": {
    "ec2": {
      "default_region": "us-east-1"
    }
  },
  "enabled_services": {
    "trusted_advisor": {
      "enabled": true,
      "note": "Available in commercial AWS"
    }
  }
}
```

## Usage

1. **Recommended**: First run the configuration setup script (optional but recommended):
   ```
   python configure.py
   ```

2. Run the main menu script:
   ```
   python stratusscan.py
   ```

3. Select the resource type you want to export from the menu

4. Choose your region preference:
   - All regions
   - Specific region (us-east-1, us-west-2, etc.)

5. Follow the prompts to configure the export

6. Find the exported file in the `output` directory

7. Optionally, use the archive feature to create a zip file of all exports

## AWS Region Selection

When prompted for regions, you can select from all AWS commercial regions including:

- **us-east-1**: US East (N. Virginia)
- **us-east-2**: US East (Ohio)
- **us-west-1**: US West (N. California)
- **us-west-2**: US West (Oregon)
- **eu-west-1**: Europe (Ireland)
- **eu-central-1**: Europe (Frankfurt)
- **ap-southeast-1**: Asia Pacific (Singapore)
- **ap-northeast-1**: Asia Pacific (Tokyo)
- And many more...

The script will validate that you're selecting valid AWS regions and provide helpful error messages if invalid regions are specified.

## Individual Export Scripts

While the main menu is the recommended way to run the export tools, you can also run individual scripts directly:

```
python scripts/ec2-export.py
```

Each script will prompt for any required information and save its output to the `output` directory.

## AWS Permissions

The scripts require read-only access to the AWS resources they're exporting. At a minimum, you'll need the following AWS permission policies:

- **ReadOnlyAccess**: For general resource access
- **IAMReadOnlyAccess**: For IAM-related exports
- **AWSSupportAccess**: For Trusted Advisor access
- **ComputeOptimizerReadOnlyAccess**: For Compute Optimizer recommendations

### Recommended IAM Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "s3:GetBucketLocation",
                "s3:GetBucketVersioning",
                "s3:ListBucket",
                "s3:GetBucketAcl",
                "s3:GetBucketPolicy",
                "rds:Describe*",
                "ecs:Describe*",
                "ecs:List*",
                "elasticloadbalancing:Describe*",
                "iam:Get*",
                "iam:List*",
                "iam:GenerateCredentialReport",
                "iam:GenerateServiceLastAccessedDetails",
                "identitystore:Describe*",
                "identitystore:List*",
                "sso:Describe*",
                "sso:List*",
                "sso-admin:Describe*",
                "sso-admin:List*",
                "ce:GetCostAndUsage",
                "ce:GetUsageReport",
                "compute-optimizer:GetRecommendations*",
                "support:DescribeTrustedAdvisor*",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## Troubleshooting

### Common Issues

**Missing Dependencies**
- Run `pip install boto3 pandas openpyxl` or let the script install them automatically when prompted

**Invalid Region Errors**
- Ensure you're using valid AWS commercial regions
- The script validates regions and provides helpful error messages

**Service Not Available Errors**
- Some services may have limited availability in certain regions
- Check the service availability in your specific AWS regions

**Permissions Issues**
- Ensure your IAM user/role has the necessary read permissions
- Work with your security team to ensure proper access

### Getting Help

1. Check the script output for specific error messages
2. Verify your AWS credentials and permissions
3. Ensure you're using valid AWS regions
4. Review the configuration file for any service-specific settings

## File Naming Conventions

All exported files follow this naming convention:

- Single resource: `ACCOUNT-NAME-RESOURCE-TYPE-export-MM.DD.YYYY.xlsx`
- With suffix: `ACCOUNT-NAME-RESOURCE-TYPE-SUFFIX-export-MM.DD.YYYY.xlsx`
- Archive: `ACCOUNT-NAME-export-MM.DD.YYYY.zip`

This naming convention helps maintain audit trails and clearly identifies exports.

## Support and Compliance

This tool is designed to work within AWS Commercial environments. Always verify that your use of this tool complies with your organization's security policies and any applicable regulations.

For questions about specific features or compliance considerations, consult with your organization's cloud security team.
