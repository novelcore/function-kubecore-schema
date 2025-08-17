# KubeCore Platform Context Function - User Guide

**Complete guide to using the KubeCore Platform Context Function in Crossplane compositions**

---

## Table of Contents

1. [Overview](#overview)
2. [Function Schema](#function-schema)
3. [Usage in Compositions](#usage-in-compositions)
4. [Query Options](#query-options)
5. [Response Format](#response-format)
6. [Caching System](#caching-system)
7. [Performance Optimization](#performance-optimization)
8. [Real-world Examples](#real-world-examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The KubeCore Platform Context Function provides intelligent, context-aware schema resolution for Crossplane compositions. It analyzes your composite resource requests and returns relevant platform configuration data, relationships, and insights to simplify composition template development.

### Key Benefits

- 🧠 **Intelligent Schema Resolution**: Automatically filters and returns only relevant schemas
- ⚡ **Performance Optimized**: Sub-100ms response times with intelligent caching
- 🔗 **Relationship Mapping**: Provides comprehensive resource relationship information
- 📊 **Context Insights**: Generates recommendations and compatibility analysis
- 🏗️ **Template Simplification**: Reduces complex resource lookups in compositions

---

## Function Schema

### Input Schema

```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Input
spec:
  query:
    resourceType: string              # Required: Type of requesting resource
    requestedSchemas: [string]        # Optional: Specific schemas to resolve
    includeRelationships: boolean     # Optional: Include relationship data (default: true)
    generateInsights: boolean         # Optional: Generate insights and recommendations (default: true)
    maxDepth: integer                # Optional: Maximum relationship traversal depth (default: 3)
    filters:                         # Optional: Schema filtering options
      environment: string            # Filter by environment type
      criticality: string            # Filter by criticality level
      tags: [string]                 # Filter by resource tags
```

### Supported Resource Types

| Resource Type | Description | Accessible Schemas |
|--------------|-------------|-------------------|
| **XApp** | Application deployments | `kubEnv`, `qualityGate`, `githubProject`, `kubeCluster` |
| **XKubeSystem** | System infrastructure | `kubeCluster`, `kubEnv`, `kubeNet`, `qualityGate` |
| **XKubEnv** | Environment configuration | `kubeCluster`, `qualityGate`, `kubeNet`, `githubProject` |
| **XKubeCluster** | Cluster management | `kubEnv`, `kubeNet`, `kubeSystem` |
| **XQualityGate** | Quality assurance | `kubEnv`, `githubProject`, `app` |
| **XGitHubProject** | Source code management | `app`, `qualityGate`, `kubEnv` |

### Available Schema Types

#### `kubEnv` - Environment Configuration
```yaml
# Example kubEnv schema data
kubEnv:
  name: "production"
  cluster:
    name: "prod-cluster-01"
    region: "us-east-1"
    version: "1.28.0"
  namespace: "applications"
  environment: "production"
  resources:
    profile: "large"
    defaults:
      requests: {cpu: "200m", memory: "256Mi"}
      limits: {cpu: "1000m", memory: "1Gi"}
  monitoring:
    enabled: true
    retention: "30d"
  backup:
    enabled: true
    schedule: "0 2 * * *"
```

#### `qualityGate` - Quality Assurance
```yaml
# Example qualityGate schema data
qualityGate:
  name: "production-quality"
  criteria:
    testCoverage: 0.85
    codeQuality: "A"
    securityScan: "passed"
    performanceThreshold: 500
  enforcement: "blocking"
  notifications:
    slack: "#quality-alerts"
    email: ["team@company.com"]
```

#### `githubProject` - Source Management
```yaml
# Example githubProject schema data
githubProject:
  name: "main-application"
  repository: "organization/main-app"
  branch: "main"
  visibility: "private"
  cicd:
    enabled: true
    workflow: ".github/workflows/ci.yml"
  security:
    secretScanning: true
    dependabot: true
```

#### `kubeCluster` - Cluster Information
```yaml
# Example kubeCluster schema data
kubeCluster:
  name: "production-cluster"
  version: "1.28.0"
  region: "us-east-1"
  nodeGroups:
    - name: "system"
      instanceType: "m5.large"
      minSize: 2
      maxSize: 10
  networking:
    vpc: "vpc-12345"
    subnets: ["subnet-abc", "subnet-def"]
  addons:
    - "aws-load-balancer-controller"
    - "cluster-autoscaler"
```

---

## Usage in Compositions

### Basic Usage Pattern

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xapp-composition
  labels:
    provider: kubecore
    service: application
spec:
  compositeTypeRef:
    apiVersion: platform.kubecore.io/v1alpha1
    kind: XApp
  
  functions:
  # Step 1: Get platform context
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

  # Step 2: Use context in subsequent functions
  - step: generate-resources
    functionRef:
      name: function-kcl
    input:
      apiVersion: krm.kcl.dev/v1alpha1
      kind: KCLInput
      spec:
        source: |
          # Access resolved platform context
          platformContext = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]
          
          # Extract environment configuration
          envConfig = platformContext.availableSchemas.kubEnv.instances[0].summary
          qualityConfig = platformContext.availableSchemas.qualityGate.instances[0].summary
          
          # Generate Kubernetes resources with context
          resources = [
            {
              apiVersion = "apps/v1"
              kind = "Deployment"
              metadata = {
                name = option("params").oxr.metadata.name
                namespace = envConfig.namespace
                labels = {
                  "app.kubernetes.io/name" = option("params").oxr.metadata.name
                  "platform.kubecore.io/environment" = envConfig.environment
                }
              }
              spec = {
                replicas = envConfig.resources.profile == "large" ? 3 : 1
                template = {
                  spec = {
                    containers = [{
                      name = "app"
                      resources = {
                        requests = envConfig.resources.defaults.requests
                        limits = envConfig.resources.defaults.limits
                      }
                      env = [
                        {name = "ENVIRONMENT", value = envConfig.environment}
                        {name = "CLUSTER_NAME", value = envConfig.cluster.name}
                        {name = "QUALITY_THRESHOLD", value = str(qualityConfig.criteria.performanceThreshold)}
                      ]
                    }]
                  }
                }
              }
            }
          ]
```

### Advanced Usage with Filtering

```yaml
- step: get-filtered-context
  functionRef:
    name: function-kubecore-platform-context
  input:
    apiVersion: context.fn.kubecore.io/v1beta1
    kind: Input
    spec:
      query:
        resourceType: "XApp"
        requestedSchemas: ["kubEnv", "qualityGate"]
        includeRelationships: true
        generateInsights: true
        maxDepth: 2
        filters:
          environment: "production"
          criticality: "high"
          tags: ["certified", "secure"]
```

---

## Query Options

### Resource Type Selection

The `resourceType` determines which schemas are accessible and how relationships are resolved:

```yaml
# For application deployments
resourceType: "XApp"
# Provides: kubEnv, qualityGate, githubProject, kubeCluster

# For system components  
resourceType: "XKubeSystem"
# Provides: kubeCluster, kubEnv, kubeNet, qualityGate

# For environment management
resourceType: "XKubEnv"  
# Provides: kubeCluster, qualityGate, kubeNet, githubProject
```

### Schema Selection Strategies

#### 1. Explicit Schema Request
```yaml
query:
  resourceType: "XApp"
  requestedSchemas: ["kubEnv", "qualityGate"]  # Only these schemas
```

#### 2. Auto-Discovery (Default)
```yaml
query:
  resourceType: "XApp"
  # requestedSchemas omitted - returns all accessible schemas
```

#### 3. Filtered Discovery
```yaml
query:
  resourceType: "XApp"
  requestedSchemas: ["kubEnv"]
  filters:
    environment: "production"  # Only production environments
```

### Relationship Configuration

```yaml
query:
  resourceType: "XApp"
  includeRelationships: true  # Include relationship mapping
  maxDepth: 3                 # Maximum traversal depth
```

**Relationship Types:**
- `dependsOn` - Direct dependencies
- `uses` - Resource utilization
- `manages` - Management relationships
- `contains` - Containment relationships

### Insight Generation

```yaml
query:
  resourceType: "XApp"
  generateInsights: true      # Generate recommendations
```

**Insight Categories:**
- `recommendations` - Best practice suggestions
- `warnings` - Potential issues or conflicts
- `optimizations` - Performance improvement opportunities
- `compliance` - Security and policy compliance status

---

## Response Format

### Complete Response Structure

```yaml
# Response is available in context at:
# context["context.fn.kubecore.io/platform-context"]

platformContext:
  requestor:
    type: "XApp"                    # Requesting resource type
    name: "my-application"          # Resource name
    namespace: "default"            # Resource namespace
  
  availableSchemas:
    kubEnv:
      metadata:
        apiVersion: "platform.kubecore.io/v1alpha1"
        kind: "XKubEnv"
        accessible: true
        relationshipPath: ["app", "kubEnv"]
      instances:
        - name: "production"
          namespace: "platform"
          summary:
            environmentType: "production"
            cluster:
              name: "prod-cluster-01"
              region: "us-east-1"
            resources:
              profile: "large"
              defaults:
                requests: {cpu: "200m", memory: "256Mi"}
                limits: {cpu: "1000m", memory: "1Gi"}
            qualityGates: ["security-scan", "performance-test"]
    
    qualityGate:
      metadata:
        apiVersion: "quality.platform.kubecore.io/v1alpha1"  
        kind: "XQualityGate"
        accessible: true
        relationshipPath: ["app", "qualityGate"]
      instances:
        - name: "production-quality"
          namespace: "quality"
          summary:
            criteria:
              testCoverage: 0.85
              codeQuality: "A"
              securityScan: "passed"
            enforcement: "blocking"
            
  relationships:
    direct:
      - type: "kubEnv"
        cardinality: "N:N"
        description: "App can deploy to multiple environments"
      - type: "githubProject"  
        cardinality: "1:1"
        description: "App belongs to a GitHub project"
    
  insights:
    recommendations:
      - "Enable monitoring for production environment"
      - "Configure backup retention for critical data"
    warnings: []
    optimizations:
      - "Consider using horizontal pod autoscaling"
    compliance:
      - status: "compliant"
        policy: "security-baseline"
```

### Accessing Response Data in KCL

```python
# Get the full platform context
platformContext = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]

# Access specific schema instances
envInstances = platformContext.availableSchemas.kubEnv.instances
firstEnv = envInstances[0] if envInstances else None

if firstEnv:
    # Use environment configuration
    clusterName = firstEnv.summary.cluster.name
    namespace = firstEnv.summary.namespace or "default"
    resourceProfile = firstEnv.summary.resources.profile
    
    # Use in resource generation
    deployment = {
        metadata = {
            namespace = namespace
            labels = {"cluster": clusterName}
        }
        spec = {
            replicas = 3 if resourceProfile == "large" else 1
        }
    }

# Access quality gate information
qualityInstances = platformContext.availableSchemas.qualityGate.instances
if qualityInstances:
    testCoverage = qualityInstances[0].summary.criteria.testCoverage
    # Use in CI/CD configuration

# Access insights
recommendations = platformContext.insights.recommendations
warnings = platformContext.insights.warnings
```

---

## Caching System

### How Caching Works

The function includes an intelligent caching system that dramatically improves performance for repeated queries:

```yaml
# Cache Configuration (via environment variables)
CACHE_TTL_SECONDS: "300"        # 5-minute cache lifetime
CACHE_MAX_ENTRIES: "1000"       # Maximum cached responses
MAX_WORKERS: "4"                # Parallel processing workers
TIMEOUT_SECONDS: "30"           # Query timeout
```

### Cache Key Generation

Cache keys are generated deterministically based on:

1. **Resource Type**: The type of requesting resource (`XApp`, `XKubeSystem`, etc.)
2. **Context References**: The specific resource references in the request
3. **Requested Schemas**: The list of schemas being requested
4. **Filter Parameters**: Any filtering options applied

```python
# Cache key example:
# MD5 hash of: "type:XApp|refs:12345|schemas:kubEnv:qualityGate"
cache_key = "a1b2c3d4e5f6789..."
```

### Cache Performance

- **Cache Hit**: <5ms response time
- **Cache Miss**: <100ms response time (full processing)
- **Hit Rate**: Typically >60% in production environments
- **Memory Usage**: ~5MB per 1000 cached entries

### Cache Invalidation

Caches automatically expire based on TTL settings:

- **Default TTL**: 300 seconds (5 minutes)
- **Automatic Cleanup**: Expired entries are periodically removed
- **Manual Cleanup**: Function restart clears all caches

### Cache Effectiveness Monitoring

Monitor cache performance through function logs:

```json
{
  "level": "info",
  "msg": "performance_metrics",
  "cache_entries": 45,
  "cache_hit_rate": 0.72,
  "total_queries": 128,
  "avg_response_time": 0.023
}
```

---

## Performance Optimization

### Query Performance Tuning

#### 1. Minimize Requested Schemas
```yaml
# Instead of requesting all schemas
requestedSchemas: ["kubEnv", "qualityGate", "githubProject", "kubeCluster"]

# Request only what you need
requestedSchemas: ["kubEnv", "qualityGate"]
```

#### 2. Use Appropriate Relationship Depth
```yaml
# For simple queries
maxDepth: 1

# For complex relationship traversal
maxDepth: 3  # Maximum recommended
```

#### 3. Apply Filters Early
```yaml
query:
  resourceType: "XApp"
  requestedSchemas: ["kubEnv"]
  filters:
    environment: "production"    # Reduces processing overhead
```

### Parallel Processing

The function automatically uses parallel processing for:
- Multiple schema resolution
- Resource reference lookups
- Relationship mapping

Configure parallel processing:
```yaml
# In deployment manifest
env:
- name: MAX_WORKERS
  value: "4"                    # Optimal for most workloads
```

### Memory Management

The function is optimized for minimal memory usage:

- **Baseline**: ~50MB memory usage
- **With Caching**: +5MB per 1000 cached entries
- **Resource Limits**: 256MB limit with safety margin

```yaml
# Recommended resource configuration
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

---

## Real-world Examples

### Example 1: Web Application Deployment

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: webapp-composition
spec:
  compositeTypeRef:
    apiVersion: platform.kubecore.io/v1alpha1
    kind: XApp
  
  functions:
  - step: get-context
    functionRef:
      name: function-kubecore-platform-context
    input:
      apiVersion: context.fn.kubecore.io/v1beta1
      kind: Input
      spec:
        query:
          resourceType: "XApp"
          requestedSchemas: ["kubEnv", "qualityGate", "githubProject"]
          filters:
            environment: "production"

  - step: generate-webapp
    functionRef:
      name: function-kcl
    input:
      apiVersion: krm.kcl.dev/v1alpha1
      kind: KCLInput
      spec:
        source: |
          import regex
          
          # Get platform context
          ctx = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]
          
          # Extract configuration
          env = ctx.availableSchemas.kubEnv.instances[0].summary
          quality = ctx.availableSchemas.qualityGate.instances[0].summary
          project = ctx.availableSchemas.githubProject.instances[0].summary
          
          appName = option("params").oxr.metadata.name
          
          # Generate Deployment
          deployment = {
            apiVersion = "apps/v1"
            kind = "Deployment"
            metadata = {
              name = appName
              namespace = env.namespace
              labels = {
                "app.kubernetes.io/name" = appName
                "platform.kubecore.io/environment" = env.environment
                "platform.kubecore.io/quality-gate" = quality.name
              }
            }
            spec = {
              replicas = 3 if env.resources.profile == "large" else 1
              selector.matchLabels = {"app": appName}
              template = {
                metadata.labels = {"app": appName}
                spec = {
                  containers = [{
                    name = appName
                    image = project.repository + ":latest"
                    resources = env.resources.defaults
                    env = [
                      {name = "NODE_ENV", value = env.environment}
                      {name = "CLUSTER_NAME", value = env.cluster.name}
                    ]
                    livenessProbe = {
                      httpGet = {path = "/health", port = 8080}
                      initialDelaySeconds = 30
                    }
                  }]
                }
              }
            }
          }
          
          # Generate Service
          service = {
            apiVersion = "v1"
            kind = "Service"
            metadata = {
              name = appName
              namespace = env.namespace
            }
            spec = {
              selector = {"app": appName}
              ports = [{port = 80, targetPort = 8080}]
              type = "ClusterIP"
            }
          }
          
          # Generate Ingress if monitoring is enabled
          ingress = {
            apiVersion = "networking.k8s.io/v1"
            kind = "Ingress"
            metadata = {
              name = appName
              namespace = env.namespace
              annotations = {
                "nginx.ingress.kubernetes.io/rewrite-target" = "/"
              }
            }
            spec = {
              rules = [{
                host = appName + "." + env.cluster.region + ".example.com"
                http.paths = [{
                  path = "/"
                  pathType = "Prefix"
                  backend.service = {name = appName, port.number = 80}
                }]
              }]
            }
          } if env.monitoring.enabled else None
          
          # Return resources
          items = [deployment, service]
          if ingress:
              items.append(ingress)
```

### Example 2: Microservice with Quality Gates

```yaml
- step: get-microservice-context
  functionRef:
    name: function-kubecore-platform-context
  input:
    apiVersion: context.fn.kubecore.io/v1beta1
    kind: Input
    spec:
      query:
        resourceType: "XApp"
        requestedSchemas: ["kubEnv", "qualityGate"]
        generateInsights: true
        filters:
          tags: ["microservice", "api"]

- step: generate-microservice
  functionRef:
    name: function-kcl
  input:
    apiVersion: krm.kcl.dev/v1alpha1
    kind: KCLInput
    spec:
      source: |
        ctx = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]
        
        # Check quality gate requirements
        quality = ctx.availableSchemas.qualityGate.instances[0].summary
        env = ctx.availableSchemas.kubEnv.instances[0].summary
        
        # Apply quality-based configuration
        deployment = {
          spec = {
            replicas = 3 if quality.criteria.testCoverage >= 0.8 else 1
            template.spec.containers[0] = {
              # High-quality services get more resources
              resources = {
                requests = {
                  cpu = "200m" if quality.criteria.codeQuality == "A" else "100m"
                  memory = "512Mi" if quality.enforcement == "blocking" else "256Mi"
                }
              }
              # Enable detailed monitoring for high-quality services
              env = [
                {name = "LOG_LEVEL", value = "debug" if quality.criteria.testCoverage >= 0.9 else "info"}
                {name = "METRICS_ENABLED", value = "true" if quality.enforcement == "blocking" else "false"}
              ]
            }
          }
        }
```

### Example 3: Multi-Environment Deployment

```yaml
- step: get-multi-env-context
  functionRef:
    name: function-kubecore-platform-context
  input:
    apiVersion: context.fn.kubecore.io/v1beta1
    kind: Input
    spec:
      query:
        resourceType: "XApp"
        requestedSchemas: ["kubEnv"]
        # Don't filter by environment - get all environments

- step: deploy-to-environments
  functionRef:
    name: function-kcl
  input:
    apiVersion: krm.kcl.dev/v1alpha1
    kind: KCLInput
    spec:
      source: |
        ctx = option("params").oxr.status.context["context.fn.kubecore.io/platform-context"]
        
        # Deploy to all available environments
        environments = ctx.availableSchemas.kubEnv.instances
        appName = option("params").oxr.metadata.name
        
        deployments = []
        for env in environments:
            envConfig = env.summary
            
            deployment = {
              apiVersion = "apps/v1"
              kind = "Deployment"
              metadata = {
                name = appName + "-" + envConfig.environment
                namespace = envConfig.namespace
                labels = {
                  "app.kubernetes.io/name" = appName
                  "platform.kubecore.io/environment" = envConfig.environment
                }
              }
              spec = {
                replicas = {
                  "production": 5,
                  "staging": 2,
                  "development": 1
                }.get(envConfig.environment, 1)
                
                template.spec.containers[0] = {
                  name = appName
                  resources = envConfig.resources.defaults
                  env = [
                    {name = "NODE_ENV", value = envConfig.environment}
                    {name = "CLUSTER_NAME", value = envConfig.cluster.name}
                  ]
                }
              }
            }
            
            deployments.append(deployment)
        
        items = deployments
```

---

## Best Practices

### 1. Query Optimization

**✅ Do:**
```yaml
# Request only needed schemas
requestedSchemas: ["kubEnv", "qualityGate"]

# Use appropriate filters
filters:
  environment: "production"
  criticality: "high"
```

**❌ Don't:**
```yaml
# Avoid requesting unnecessary schemas
requestedSchemas: ["kubEnv", "qualityGate", "githubProject", "kubeCluster", "kubeNet"]

# Avoid overly broad queries without filters
# (This can impact performance)
```

### 2. Error Handling

```yaml
# Always check for schema availability in KCL
envInstances = platformContext.availableSchemas.kubEnv.instances
if envInstances and len(envInstances) > 0:
    envConfig = envInstances[0].summary
    namespace = envConfig.namespace
else:
    # Fallback configuration
    namespace = "default"
```

### 3. Caching Strategy

**For Frequently Accessed Resources:**
```yaml
# Use consistent naming for better cache hits
metadata:
  name: "my-app-production"  # Consistent naming pattern

# Request schemas in consistent order
requestedSchemas: ["kubEnv", "qualityGate"]  # Alphabetical order
```

### 4. Resource Reference Patterns

**In Composite Resource Definitions:**
```yaml
spec:
  kubEnvRefs:
    - name: "production"
      namespace: "platform"
  qualityGateRefs:
    - name: "high-security"
      namespace: "quality"
```

### 5. Composition Structure

```yaml
functions:
# Always get context first
- step: get-platform-context
  functionRef:
    name: function-kubecore-platform-context
  # ... context configuration

# Then use context in subsequent steps  
- step: generate-resources
  functionRef:
    name: function-kcl
  # ... resource generation using context
```

### 6. Performance Monitoring

```yaml
# Monitor function performance in logs
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "performance_metrics"
```

### 7. Testing and Validation

```yaml
# Test compositions with sample data
apiVersion: platform.kubecore.io/v1alpha1
kind: XApp
metadata:
  name: test-app
spec:
  kubEnvRefs:
    - name: "test-env"
      namespace: "platform"
  qualityGateRefs:
    - name: "basic-quality"
      namespace: "quality"
```

---

## Troubleshooting

### Common Issues

#### 1. Schema Not Accessible

**Problem:** Requested schema not found in response
```yaml
# Response shows empty or missing schema
availableSchemas: {}
```

**Solution:** Check resource type compatibility
```yaml
# Ensure resource type can access requested schemas
# XApp can access: kubEnv, qualityGate, githubProject
# XKubeSystem can access: kubeCluster, kubEnv, kubeNet

query:
  resourceType: "XApp"           # Check this matches your composite
  requestedSchemas: ["kubEnv"]   # Ensure this is accessible
```

#### 2. Cache Miss Performance

**Problem:** Slow response times consistently
```yaml
# Logs show low cache hit rate
"cache_hit_rate": 0.15
```

**Solution:** Improve cache key consistency
```yaml
# Use consistent resource naming
metadata:
  name: "app-prod-v1"    # Instead of random names

# Request schemas in same order
requestedSchemas: ["kubEnv", "qualityGate"]  # Consistent ordering
```

#### 3. Reference Resolution Failures

**Problem:** Empty instances in schema response
```yaml
availableSchemas:
  kubEnv:
    instances: []  # Empty instances
```

**Solution:** Check resource references
```yaml
# Ensure references exist and are correctly formatted
spec:
  kubEnvRefs:
    - name: "existing-env"      # Must exist
      namespace: "platform"     # Correct namespace
```

#### 4. Memory or Performance Issues

**Problem:** Function consuming too much memory or timing out
```yaml
# Logs show high memory usage or timeouts
"memory_usage": "200MB"
"errors": 5
```

**Solution:** Optimize resource limits and queries
```yaml
# Reduce query complexity
maxDepth: 1                     # Limit relationship depth
requestedSchemas: ["kubEnv"]    # Request fewer schemas

# Increase resource limits
resources:
  limits:
    memory: "512Mi"             # Increase if needed
    cpu: "1000m"
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```yaml
# In function deployment
env:
- name: LOG_LEVEL
  value: "DEBUG"
```

Debug output includes:
- Cache hit/miss details
- Schema resolution steps  
- Performance timing
- Error stack traces

### Performance Analysis

```bash
# Monitor cache effectiveness
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "cache_stats"

# Check response times
kubectl logs deployment/function-kubecore-platform-context -n crossplane-system | grep "response_time"

# Monitor memory usage
kubectl top pods -l app.kubernetes.io/name=function-kubecore-platform-context -n crossplane-system
```

### Support Resources

- **Function Logs**: `kubectl logs deployment/function-kubecore-platform-context -n crossplane-system`
- **Performance Metrics**: Check function logs for JSON-formatted performance data
- **Composition Debugging**: Use `kubectl describe composite` to see function execution results
- **Schema Validation**: Verify resource references exist with `kubectl get <resource-type> -n <namespace>`

---

## Advanced Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `CACHE_TTL_SECONDS` | Cache entry lifetime | `300` | `600` |
| `CACHE_MAX_ENTRIES` | Maximum cache size | `1000` | `2000` |
| `MAX_WORKERS` | Parallel processing workers | `4` | `8` |
| `TIMEOUT_SECONDS` | Query timeout | `30` | `60` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG` |

### Custom Resource Labels

Add labels to composite resources for better caching and filtering:

```yaml
metadata:
  labels:
    platform.kubecore.io/environment: "production"
    platform.kubecore.io/criticality: "high"  
    platform.kubecore.io/team: "backend"
```

---

**This completes the comprehensive user guide for the KubeCore Platform Context Function. For additional support, refer to the main README.md or check the function logs for detailed debugging information.**