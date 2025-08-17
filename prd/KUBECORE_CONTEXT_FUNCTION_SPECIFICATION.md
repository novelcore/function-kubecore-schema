# KubeCore Platform Context Function Specification

## Executive Summary

This document specifies a comprehensive Crossplane function that provides intelligent context-aware schema resolution for the KubeCore platform. The function analyzes composition contexts and returns relevant platform schemas, enabling compositions to make informed decisions without complex resource lookups.

## Architecture Overview

### Platform Resource Hierarchy

```
GitHubProvider (1:N) → GitHubProject (1:1) → KubeCluster
                                        ↓
KubeNet (1:N) → KubeCluster (1:1) → KubeSystem
                     ↓
                KubEnv (1:N) ← QualityGate (N:N)
                     ↓
GitHubApp (1:1) → App (N:N) → KubEnv
```

### Resource Relationships

#### Core Relationships
- **GitHubProvider**: Contains credentials and semantics for GitHub organization
- **GitHubProject**: Software product with GitOps repository, teams, and permissions
- **KubeNet**: Network infrastructure (VPC, DNS) shared across multiple projects
- **KubeCluster**: Kubernetes cluster (1:1 with GitHubProject, references KubeNet)
- **KubeSystem**: Platform tools runtime (ArgoCD, Crossplane, etc.) on KubeCluster
- **KubEnv**: Deployment environment with app node groups on KubeCluster
- **QualityGate**: Reusable validation workflows applicable to environments/apps
- **GitHubApp**: Source control for software component (1:1 with App)
- **App**: Kubernetes application deployment semantic (references multiple KubEnvs)

#### Cardinality Rules
- GitHubProvider → GitHubProject: **1:N**
- GitHubProject → KubeCluster: **1:1** 
- KubeNet → KubeCluster: **1:N**
- KubeCluster → KubeSystem: **1:1**
- KubeCluster → KubEnv: **1:N**
- GitHubApp → App: **1:1**
- App → KubEnv: **N:N** (app can deploy to multiple environments)
- QualityGate → KubEnv: **N:N** (gates are reusable across environments)
- QualityGate → App: **N:N** (apps can have specific quality gate overrides)

## Schema Definition

### Platform Schema Structure

```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: PlatformSchema
spec:
  # Core resource schemas with full OpenAPI definitions
  resources:
    githubProvider:
      schema: # Full XGitHubProvider OpenAPI schema
      relationships:
        owns: [githubProject]
    
    githubProject:
      schema: # Full XGitHubProject OpenAPI schema  
      relationships:
        belongsTo: [githubProvider]
        owns: [kubeCluster, githubApp, app]
        
    kubeNet:
      schema: # Full XKubeNet OpenAPI schema
      relationships:
        supports: [kubeCluster]
        
    kubeCluster:
      schema: # Full XKubeCluster OpenAPI schema
      relationships:
        belongsTo: [githubProject]
        uses: [kubeNet]
        hosts: [kubeSystem, kubEnv]
        
    kubeSystem:
      schema: # Full XKubeSystem OpenAPI schema
      relationships:
        runsOn: [kubeCluster]
        
    kubEnv:
      schema: # Full XKubEnv OpenAPI schema
      relationships:
        runsOn: [kubeCluster]
        uses: [qualityGate]
        hosts: [app]
        
    qualityGate:
      schema: # Full XQualityGate OpenAPI schema
      relationships:
        appliesTo: [kubEnv, app]
        
    githubApp:
      schema: # Full XGitHubApp OpenAPI schema
      relationships:
        belongsTo: [githubProject]
        sources: [app]
        
    app:
      schema: # Full XApp OpenAPI schema
      relationships:
        belongsTo: [githubProject]
        sourcedBy: [githubApp]
        deploysTo: [kubEnv]
        uses: [qualityGate]

  # Computed relationships for efficient traversal
  hierarchy:
    # Top-down ownership chains
    githubProvider: [githubProject, kubeCluster, kubeSystem, kubEnv, githubApp, app]
    githubProject: [kubeCluster, kubeSystem, kubEnv, githubApp, app]
    kubeCluster: [kubeSystem, kubEnv]
    
    # Bottom-up dependency chains  
    app: [githubApp, githubProject, githubProvider, kubEnv, kubeCluster, kubeNet, kubeSystem]
    kubEnv: [kubeCluster, githubProject, githubProvider, kubeNet, kubeSystem]
    kubeSystem: [kubeCluster, githubProject, githubProvider, kubeNet]
```

## Function Interface

### Input Specification

```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Input
spec:
  # Query configuration
  query:
    # What type of resource is requesting context
    resourceType: string # e.g., "XApp", "XKubeSystem", "XKubEnv"
    
    # What specific schemas are needed (optional - defaults to all accessible)
    requestedSchemas: []string # e.g., ["kubEnv", "qualityGate", "githubProject"]
    
    # Whether to include full schemas or just metadata
    includeFullSchemas: boolean # default: true
    
    # Whether to include relationship traversal paths
    includeRelationshipPaths: boolean # default: true
    
    # Maximum depth for relationship traversal
    maxDepth: int # default: 10
    
  # Context hints (extracted from observed composite)
  context:
    # References found in the composite resource
    references:
      githubProjectRef: 
        name: string
        namespace: string
      kubEnvRefs: 
        - name: string
          namespace: string
      qualityGateRefs:
        - name: string  
          namespace: string
      # ... other refs
      
    # Resource metadata
    metadata:
      name: string
      namespace: string
      labels: map[string]string
      annotations: map[string]string
```

### Output Specification

```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Output
spec:
  # Resolved platform context
  platformContext:
    # Requesting resource information
    requestor:
      type: string
      name: string
      namespace: string
      
    # Available schemas based on resource type and relationships
    availableSchemas:
      githubProvider:
        schema: # Full OpenAPI schema if includeFullSchemas=true
        metadata:
          apiVersion: string
          kind: string
          accessible: boolean
          relationshipPath: []string # e.g., ["app", "githubProject", "githubProvider"]
          
      githubProject:
        schema: # Full schema
        metadata:
          apiVersion: string
          kind: string  
          accessible: boolean
          relationshipPath: []string
          
      kubEnv:
        schema: # Full schema
        metadata:
          apiVersion: string
          kind: string
          accessible: boolean
          relationshipPath: []string
          instances: # Resolved instances from references
            - name: string
              namespace: string
              summary: # Key fields from status
                environmentType: string
                resources: object
                qualityGates: []object
                
      qualityGate:
        schema: # Full schema
        metadata:
          apiVersion: string
          kind: string
          accessible: boolean
          relationshipPath: []string
          instances:
            - name: string
              namespace: string
              summary:
                key: string
                category: string
                severity: string
                applicability: object
                
      # ... other accessible schemas
      
    # Relationship mappings for the requesting resource
    relationships:
      # Direct relationships (what this resource can reference)
      direct:
        - type: string # e.g., "kubEnv"
          cardinality: string # e.g., "N:N"
          description: string
          
      # Indirect relationships (accessible through traversal)
      indirect:
        - type: string
          path: []string # traversal path
          cardinality: string
          description: string
          
    # Computed insights
    insights:
      # Suggested references based on common patterns
      suggestedReferences:
        - type: string
          reason: string
          candidates: []object
          
      # Validation rules
      validationRules:
        - rule: string
          description: string
          
      # Best practices
      recommendations:
        - category: string
          suggestion: string
          impact: string # "low", "medium", "high"
```

## Query Mechanisms & Context Resolution

### Context-Aware Query Processing

The function implements intelligent query processing based on the requesting resource type:

#### 1. App Composition Queries
When `resourceType: "XApp"`:
```yaml
# Automatically provides:
availableSchemas: [kubEnv, qualityGate, githubProject, githubApp, kubeCluster, kubeNet, kubeSystem, githubProvider]

# Special processing:
- Resolves all referenced KubEnv instances with their configurations
- Merges quality gates from KubEnv + App-specific overrides  
- Provides GitHubProject context for GitOps integration
- Computes resource inheritance chains (KubEnv defaults → App overrides)
```

#### 2. KubeSystem Composition Queries  
When `resourceType: "XKubeSystem"`:
```yaml
# Automatically provides:
availableSchemas: [kubeCluster, githubProject, kubeNet, githubProvider]

# Special processing:
- Resolves KubeCluster configuration and provider configs
- Provides network configuration from referenced KubeNet
- GitHubProject context for GitOps webhook configuration
- DNS and ingress configuration derivation
```

#### 3. KubEnv Composition Queries
When `resourceType: "XKubEnv"`:
```yaml  
# Automatically provides:
availableSchemas: [kubeCluster, qualityGate, githubProject, kubeNet, kubeSystem]

# Special processing:
- Resolves QualityGate applicability for environment type
- Provides cluster capacity and node group information
- Network and DNS configuration inheritance
```

### Schema Filtering & Optimization

The function implements smart schema filtering to return only relevant information:

```yaml
# For App requesting KubEnv schema:
kubEnv:
  schema:
    # Only includes fields relevant to App deployment:
    spec:
      environmentType: {...}
      resources: {...}
      environmentConfig: {...}
      qualityGates: {...}
      # Excludes internal cluster management fields
  instances:
    - name: "demo-dev"
      summary:
        environmentType: "dev"
        resources:
          profile: "small"
          defaults: {...}
        qualityGates: [...]
```

## Implementation Architecture

### Function Components

#### 1. Schema Registry
```go
type SchemaRegistry struct {
    schemas map[string]*openapi3.Schema
    relationships map[string][]Relationship
    hierarchy map[string][]string
}

func (sr *SchemaRegistry) GetAccessibleSchemas(resourceType string) []string
func (sr *SchemaRegistry) ResolveRelationshipPath(from, to string) []string
func (sr *SchemaRegistry) FilterSchema(schema *openapi3.Schema, context QueryContext) *openapi3.Schema
```

#### 2. Context Resolver
```go
type ContextResolver struct {
    registry *SchemaRegistry
    client client.Client
}

func (cr *ContextResolver) ResolveContext(input *Input) (*Output, error)
func (cr *ContextResolver) ResolveReferences(refs []ResourceRef) ([]ResolvedInstance, error)
func (cr *ContextResolver) ComputeInsights(context PlatformContext) Insights
```

#### 3. Query Processor
```go
type QueryProcessor struct {
    resolver *ContextResolver
}

func (qp *QueryProcessor) ProcessAppQuery(input *Input) (*Output, error)
func (qp *QueryProcessor) ProcessKubeSystemQuery(input *Input) (*Output, error)
func (qp *QueryProcessor) ProcessKubEnvQuery(input *Input) (*Output, error)
```

### Performance Optimizations

1. **Schema Caching**: Pre-computed schema subsets for common query patterns
2. **Relationship Indexing**: Fast lookup of relationship paths
3. **Reference Resolution Batching**: Batch Kubernetes API calls for efficiency
4. **Incremental Updates**: Only recompute changed relationships

## Usage Examples

### Example 1: App Composition Context Query

**Input:**
```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Input
spec:
  query:
    resourceType: "XApp"
    requestedSchemas: ["kubEnv", "qualityGate", "githubProject"]
    includeFullSchemas: true
  context:
    references:
      githubAppRef:
        name: "art-api"
        namespace: "default"
    metadata:
      name: "art-api"
      namespace: "default"
```

**Output:**
```yaml
apiVersion: context.fn.kubecore.io/v1beta1  
kind: Output
spec:
  platformContext:
    requestor:
      type: "XApp"
      name: "art-api"
      namespace: "default"
    availableSchemas:
      kubEnv:
        schema: # Full XKubEnv schema
        metadata:
          accessible: true
          relationshipPath: ["app", "kubEnv"]
        instances:
          - name: "demo-dev"
            namespace: "test"
            summary:
              environmentType: "dev"
              resources:
                profile: "small"
                defaults:
                  requests: {cpu: "100m", memory: "128Mi"}
                  limits: {cpu: "500m", memory: "256Mi"}
              qualityGates:
                - ref: {name: "smoke-test-gate"}
                  phase: "active"
                  required: true
      qualityGate:
        schema: # Full XQualityGate schema
        instances:
          - name: "smoke-test-gate"
            summary:
              key: "smoke-test"
              category: "testing"
              applicability:
                environments: ["dev", "staging", "prod"]
    relationships:
      direct:
        - type: "kubEnv"
          cardinality: "N:N"
          description: "App can deploy to multiple environments"
    insights:
      recommendations:
        - category: "resource-optimization"
          suggestion: "Consider overriding memory requests for Python applications"
          impact: "medium"
```

### Example 2: KubeSystem Composition Context Query

**Input:**
```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Input
spec:
  query:
    resourceType: "XKubeSystem"
    includeFullSchemas: false
  context:
    references:
      kubeClusterRef:
        name: "demo-cluster"
        namespace: "test"
```

**Output:**
```yaml
apiVersion: context.fn.kubecore.io/v1beta1
kind: Output
spec:
  platformContext:
    availableSchemas:
      kubeCluster:
        metadata:
          accessible: true
          relationshipPath: ["kubeSystem", "kubeCluster"]
        instances:
          - name: "demo-cluster"
            summary:
              region: "eu-west-3"
              version: "1.33"
              githubProjectRef: {name: "demo-project"}
              kubeNetRef: {name: "demo-network"}
      kubeNet:
        metadata:
          accessible: true
          relationshipPath: ["kubeSystem", "kubeCluster", "kubeNet"]
        instances:
          - name: "demo-network"
            summary:
              dns: {domain: "sexy.kubecore.eu"}
              vpc: {cidr: "10.0.0.0/16"}
    insights:
      suggestedReferences:
        - type: "externalDNS"
          reason: "KubeNet provides hosted zone for automatic DNS management"
```

## Function Development Prompt

### Objective
Develop a Crossplane function named `function-kubecore-platform-context` that provides intelligent, context-aware schema resolution for KubeCore platform compositions.

### Core Requirements

#### 1. Schema Management
- **Static Schema Loading**: Load all XRD schemas from KubeCore platform at startup
- **Relationship Mapping**: Build relationship graph based on resource references and ownership
- **Schema Filtering**: Return only relevant schema portions based on requesting resource type
- **Performance**: Sub-100ms response time for typical queries

#### 2. Context Resolution
- **Reference Resolution**: Resolve Kubernetes resource references to actual instances
- **Relationship Traversal**: Navigate resource relationships to find accessible schemas
- **Instance Summarization**: Provide key status information from resolved resources
- **Caching**: Implement intelligent caching for frequently accessed resources

#### 3. Query Intelligence  
- **Resource-Type Awareness**: Provide different schema sets based on requesting composition
- **Depth Control**: Support configurable relationship traversal depth
- **Optimization Hints**: Suggest best practices and optimizations
- **Validation Rules**: Provide context-aware validation recommendations

#### 4. Integration Points
- **Crossplane Function Framework**: Use standard function interfaces and patterns
- **Kubernetes Client**: Efficient resource resolution with batching and caching
- **OpenAPI Schema Processing**: Parse and filter OpenAPI v3 schemas
- **Error Handling**: Graceful degradation when resources are not accessible

### Technical Specifications

#### Language & Framework
- **Go 1.21+** with Crossplane function-sdk-go
- **Controller-runtime** for Kubernetes client operations
- **OpenAPI v3** libraries for schema processing
- **Structured logging** with contextual information

#### Key Interfaces
```go
// Main function entry point
func (f *Function) RunFunction(ctx context.Context, req *fnv1beta1.RunFunctionRequest) (*fnv1beta1.RunFunctionResponse, error)

// Schema registry for platform resources
type SchemaRegistry interface {
    LoadSchemas(ctx context.Context) error
    GetSchema(resourceType string) (*openapi3.Schema, error)
    GetAccessibleSchemas(fromType string) ([]string, error)
    GetRelationshipPath(from, to string) ([]string, error)
}

// Context resolver for resource relationships
type ContextResolver interface {
    ResolveContext(ctx context.Context, input *Input) (*Output, error)
    ResolveReferences(ctx context.Context, refs []ResourceRef) ([]ResolvedInstance, error)
    ComputeInsights(ctx context.Context, platformContext *PlatformContext) (*Insights, error)
}
```

#### Configuration
```yaml
# Function configuration
apiVersion: pkg.crossplane.io/v1beta1
kind: Function
metadata:
  name: function-kubecore-platform-context
spec:
  package: xpkg.upbound.io/kubecore/function-platform-context:v1.0.0
  packagePullPolicy: IfNotPresent
  revisionActivationPolicy: Automatic
  revisionHistoryLimit: 1
```

### Development Guidelines

#### 1. Schema Processing
- Load XRD schemas from embedded resources or configmap
- Parse OpenAPI v3 schemas with proper validation
- Build relationship graph from reference field analysis
- Implement schema filtering based on access patterns

#### 2. Resource Resolution
- Use controller-runtime client with proper caching
- Implement batch resolution for multiple references
- Handle cross-namespace resource access appropriately
- Provide graceful fallbacks for inaccessible resources

#### 3. Performance Optimization
- Pre-compute common relationship paths
- Cache resolved resource summaries with TTL
- Use streaming for large schema responses
- Implement circuit breakers for external dependencies

#### 4. Error Handling
- Partial success patterns (some schemas available, others not)
- Clear error messages with actionable guidance
- Logging with structured context for debugging
- Graceful degradation when Kubernetes API is slow

#### 5. Testing Strategy
- Unit tests for schema processing and relationship resolution
- Integration tests with mock Kubernetes resources
- Performance tests with large resource graphs
- End-to-end tests with real KubeCore compositions

### Expected Deliverables

1. **Function Implementation**: Complete Go implementation with all interfaces
2. **Schema Definitions**: Input/Output CRDs and OpenAPI schemas
3. **Documentation**: API reference and usage examples
4. **Test Suite**: Comprehensive test coverage with benchmarks
5. **Deployment Manifests**: Kubernetes manifests for function deployment
6. **Performance Benchmarks**: Latency and memory usage characteristics

### Success Criteria

1. **Functionality**: Successfully provides context for all KubeCore composition types
2. **Performance**: <100ms response time for typical queries, <500ms for complex traversals
3. **Reliability**: 99.9% success rate with proper error handling and fallbacks
4. **Usability**: Clear API with helpful error messages and documentation
5. **Integration**: Seamless integration with existing Crossplane function pipeline

This function will significantly simplify KubeCore compositions by providing intelligent, context-aware access to platform schemas and relationships, enabling more sophisticated and maintainable infrastructure as code patterns.
