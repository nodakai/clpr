import { Filters as QueryFilters } from '../query-builder';

export type Filters = QueryFilters;

// AWS Regions grouped by geography
export const AWS_REGIONS = {
  'US East': ['us-east-1', 'us-east-2'],
  'US West': ['us-west-1', 'us-west-2'],
  'Canada': ['ca-central-1'],
  'Europe': ['eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1', 'eu-south-1'],
  'Asia Pacific': ['ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-northeast-2', 'ap-south-1', 'ap-east-1'],
  'South America': ['sa-east-1'],
  'Africa': ['af-south-1'],
  'Middle East': ['me-south-1'],
  'China': ['cn-north-1', 'cn-northwest-1'],
  'AWS GovCloud': ['us-gov-east-1', 'us-gov-west-1'],
  'AWS ISO': ['iso-b-1', 'iso-e-1'],
};

// Service options
export const SERVICES = [
  'ec2',
  'rds',
  'lambda',
  's3',
  'elasticache',
  'redshift',
  'opensearch',
];

// OS options
export const OS_OPTIONS = ['Linux', 'Windows', 'RHEL', 'SUSE'];

// Tenancy options
export const TENANCY_OPTIONS = ['Shared', 'Dedicated', 'Host'];

// Purchase option types
export const PURCHASE_OPTIONS = ['OnDemand', 'Reserved'];

// Storage options (common AWS storage types)
export const STORAGE_OPTIONS = [
  'gp2',
  'gp3',
  'io1',
  'io2',
  'io2 Block Express',
  'sc1',
  'st1',
  'Instance Store',
  'EFS',
  'FSx',
  'S3',
];
