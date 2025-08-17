# KubeCore Platform Context Function

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Crossplane](https://img.shields.io/badge/Crossplane-v1.14%2B-green.svg)](https://crossplane.io/)

## Overview

The KubeCore Platform Context Function provides intelligent, context-aware schema resolution for KubeCore platform compositions. It enables compositions to access platform schemas and relationships without complex resource lookups, significantly simplifying composition templates while improving maintainability and performance.

### Key Features

- **Intelligent Schema Resolution**: Automatically resolves and filters platform schemas based on resource type and context
- **Resource Relationship Mapping**: Provides comprehensive relationship information between platform resources  
- **Performance Optimized**: Built-in caching, parallel processing, and sub-100ms response times
- **Context-Aware**: Generates insights and recommendations based on requesting resource context
- **Production Ready**: Comprehensive error handling, monitoring, and deployment manifests

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Composition   │───▶│  Context Query   │───▶│  Platform Context  │
│    Template     │    │   Processing     │    │     Response        │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Schema Registry │
                       │  + Resource      │
                       │   Resolution     │
                       │  + Insights      │
                       └──────────────────┘
```

## Installation

### Prerequisites

- Crossplane v1.14.0 or later
- Kubernetes cluster with RBAC enabled

### Deploy the Function

```bash
# Apply the function and configuration
kubectl apply -f manifests/function.yaml

# Verify deployment
kubectl get functions -n crossplane-system
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system
```

### Verify Installation

```bash
# Check function status
kubectl describe function function-kubecore-platform-context -n crossplane-system

# View function logs
kubectl logs -l app.kubernetes.io/name=function-kubecore-platform-context -n crossplane-system
```

## Usage Examples

### Basic Usage

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xapp-composition
spec:
  compositeTypeRef:
    apiVersion: platform.kubecore.io/v1alpha1
    kind: XApp
  functions:
  - step: get-platform-context
    functionRef:
      name: function-kubecore-platform-context
    input:
      apiVersion: context.fn.kubecore.io/v1beta1
      kind: Input
      spec:
        query:
          resourceType: "XApp"
          requestedSchemas: ["kubEnv", "qualityGate"]
```

### Advanced Query with Multiple Resources

```yaml
- step: get-platform-context
  functionRef:
    name: function-kubecore-platform-context
  input:
    apiVersion: context.fn.kubecore.io/v1beta1
    kind: Input
    spec:
      query:
        resourceType: "XApp"
        requestedSchemas: ["kubEnv", "qualityGate", "githubProject"]
        includeRelationships: true
        generateInsights: true
```

### Using Context in Subsequent Steps

```yaml
- step: create-deployment
  functionRef:
    name: function-kcl
  input:
    apiVersion: krm.kcl.dev/v1alpha1
    kind: KCLInput
    spec:
      source: |
        # Access resolved context
        platformContext = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]
        
        # Use kubEnv schema data
        envConfig = platformContext.schemas.kubEnv
        namespace = envConfig.namespace
        cluster = envConfig.cluster.name
        
        # Create deployment with context
        deployment = {
          apiVersion = "apps/v1"
          kind = "Deployment"
          metadata = {
            name = "my-app"
            namespace = namespace
          }
          spec = {
            template = {
              spec = {
                containers = [{
                  name = "app"
                  env = [
                    {name = "CLUSTER_NAME", value = cluster}
                    {name = "ENVIRONMENT", value = envConfig.environment}
                  ]
                }]
              }
            }
          }
        }
```

## Response Format

The function provides context through the `context.fn.kubecore.io/platform-context` key:

```yaml
platformContext:
  schemas:
    kubEnv:
      name: "production"
      cluster:
        name: "prod-cluster"
        region: "us-east-1"
      namespace: "apps"
      environment: "production"
    qualityGate:
      name: "high-quality"
      criteria:
        testCoverage: 0.8
        codeQuality: "A"
        securityScan: "passed"
  relationships:
    kubEnv:
      - type: "dependsOn"
        resource: "infrastructure/vpc-prod"
        relationship: "network-dependency"
  summary:
    resolvedSchemas: 2
    resourceCount: 1
    processingTime: "45ms"
  insights:
    recommendations:
      - "Consider enabling monitoring for production environment"
      - "Quality gate threshold is appropriate for production workloads"
    warnings: []
    compatibility: "fully-compatible"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_TTL_SECONDS` | Cache time-to-live in seconds | `300` |
| `CACHE_MAX_ENTRIES` | Maximum cache entries | `1000` |
| `MAX_WORKERS` | Maximum parallel workers | `4` |
| `TIMEOUT_SECONDS` | Operation timeout | `30` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARN, ERROR) | `INFO` |

### ConfigMap Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: function-kubecore-config
data:
  config.yaml: |
    cache:
      ttl_seconds: 300
      max_entries: 1000
    performance:
      max_workers: 4
      timeout_seconds: 30
    logging:
      level: INFO
      format: json
    features:
      parallel_processing: true
      intelligent_caching: true
      performance_monitoring: true
```

## Performance Characteristics

### Response Times
- **Typical Query**: <50ms
- **Complex Query (3+ schemas)**: <100ms
- **Cached Query**: <5ms
- **Concurrent Queries**: 100+ queries/second

### Resource Usage
- **Memory**: <50MB typical, <128MB limit
- **CPU**: <100m typical, <500m limit
- **Cache Hit Rate**: >80% typical workloads

### Scalability
- **Horizontal Scaling**: 2+ replicas supported
- **Concurrent Processing**: 4+ parallel workers
- **Cache Size**: 1000+ entries default

## Monitoring and Observability

### Health Checks

```bash
# Check function health
kubectl get pods -l app.kubernetes.io/name=function-kubecore-platform-context -n crossplane-system

# View detailed status
kubectl describe deployment function-kubecore-platform-context -n crossplane-system
```

### Metrics

The function provides metrics through logs and can integrate with monitoring systems:

```json
{
  "level": "info",
  "msg": "performance_metrics",
  "total_queries": 150,
  "avg_response_time": 0.045,
  "cache_hit_rate": 0.82,
  "concurrent_operations": 8
}
```

### Logging

Structured JSON logging is enabled by default:

```bash
# View function logs
kubectl logs -f deployment/function-kubecore-platform-context -n crossplane-system

# Filter for specific events
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "query_completed"
```

## Troubleshooting

### Common Issues

#### Function Not Starting

```bash
# Check deployment status
kubectl get deployment function-kubecore-platform-context -n crossplane-system

# Check pod logs for errors
kubectl logs -l app.kubernetes.io/name=function-kubecore-platform-context -n crossplane-system
```

**Common causes:**
- Missing RBAC permissions
- Invalid configuration
- Resource limits too low

#### Query Timeouts

```bash
# Check timeout configuration
kubectl get configmap function-kubecore-config -n crossplane-system -o yaml

# Increase timeout if needed
kubectl patch configmap function-kubecore-config -n crossplane-system --patch '
data:
  config.yaml: |
    performance:
      timeout_seconds: 60
'
```

#### Poor Performance

```bash
# Check cache statistics in logs
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "cache_stats"

# Verify resource limits
kubectl describe deployment function-kubecore-platform-context -n crossplane-system
```

**Performance tuning:**
- Increase cache TTL for stable environments
- Add more replicas for high-load scenarios  
- Increase resource limits if CPU/memory constrained

#### Schema Resolution Failures

```bash
# Check for schema resolution errors
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "schema_error"

# Verify RBAC permissions
kubectl auth can-i get xkubenenvs --as=system:serviceaccount:crossplane-system:function-kubecore-platform-context
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
kubectl patch configmap function-kubecore-config -n crossplane-system --patch '
data:
  config.yaml: |
    logging:
      level: DEBUG
'

# Restart function to apply changes
kubectl rollout restart deployment function-kubecore-platform-context -n crossplane-system
```

## Development

### Local Development

```bash
# Clone the repository
git clone https://github.com/kubecore/function-kubecore-platform-context.git
cd function-kubecore-platform-context

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run performance tests
pytest tests/test_performance.py -v
```

### Building

```bash
# Build the function package
docker build -t function-kubecore-platform-context .

# Test locally
docker run --rm function-kubecore-platform-context
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/kubecore/function-kubecore-platform-context/issues)
- **Documentation**: [KubeCore Documentation](https://docs.kubecore.eu)
- **Community**: [KubeCore Slack](https://kubecore.slack.com)