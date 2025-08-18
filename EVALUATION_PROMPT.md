# KubeCore Transitive Discovery Function - Evaluation Prompt

## 📋 **Evaluation Task**

You are tasked with evaluating a recently implemented **Transitive Discovery** feature for the KubeCore Platform Context Function. This is a sophisticated Crossplane Composition Function that enables intelligent resource discovery through multi-hop relationship traversal.

## 🎯 **What You Need to Evaluate**

### **Core Functionality**
Evaluate whether the transitive discovery implementation successfully discovers related Kubernetes custom resources that are not directly referenced but connected through transitive relationships.

### **Expected Behavior**
The function should discover resources following these relationship chains:
```
XGitHubProject(demo-project) 
├── 1-hop: XKubeCluster(demo-cluster)     [via githubProjectRef]
├── 2-hop: XKubEnv(demo-dev)              [via githubProjectRef → kubeClusterRef] 
└── 3-hop: XApp(art-api)                  [via githubProjectRef → kubeClusterRef → kubenvRef]
```

## 🔍 **Evaluation Steps**

### **Step 1: Verify Function Deployment**
```bash
kubectl get pods -n crossplane-system | grep kubecore
```
**Expected**: Function pods should be `Running` (not `CrashLoopBackOff`)

### **Step 2: Check Function Logs**
```bash
kubectl logs function-kubecore-schema-<pod-id> -n crossplane-system --tail=50
```
**Look for**:
- ✅ "K8s client connected successfully"
- ✅ "Starting transitive discovery for XGitHubProject: demo-project"
- ✅ "Found X [ResourceType] resources"
- ✅ "Set platform context with N schemas" (where N > 0)

### **Step 3: Test with Composition**
Apply the test composition:
```bash
kubectl apply -f working-transitive-test.yaml
kubectl apply -f working-test-claim.yaml
```

Monitor:
```bash
kubectl get transitivediscoverytest working-transitive-test -n default
```
**Expected**: Should show `SYNCED=True` and `READY=True`

### **Step 4: Verify Transitive Discovery Output**
Check function logs during test execution:
```bash
kubectl logs -f function-kubecore-schema-<pod-id> -n crossplane-system
```

**Success Indicators**:
- ✅ "Transitive discovery completed: found X resources across Y types"
- ✅ No "Custom objects API client not initialized" errors
- ✅ No "Early termination: discovered 0 resources"

## 📊 **Success Criteria**

### **Critical Success Factors**
1. **Function Startup**: Pods start without crashing
2. **K8s Connectivity**: Client connects to cluster successfully
3. **Resource Discovery**: Finds real cluster resources through transitive relationships
4. **Schema Resolution**: Returns platform context with discovered schemas
5. **Error Handling**: Graceful failure with informative logging

### **Performance Indicators**
- Function execution completes in < 5 seconds
- Memory usage remains stable
- No resource leaks or connection issues

## 🧪 **Test Scenarios**

### **Primary Test Case**
- **Resource Type**: `XGitHubProject`
- **Target Resource**: `demo-project` in namespace `test`
- **Expected Discoveries**:
  - `XKubeCluster`: demo-cluster (1-hop)
  - `XKubEnv`: demo-dev (2-hop) 
  - `XApp`: art-api (3-hop)

### **Verification Commands**
```bash
# Verify the resource chain exists
kubectl get githubprojects.github.platform.kubecore.io demo-project -n test
kubectl get kubecluster demo-cluster -n test
kubectl get kubenv demo-dev -n test  
kubectl get app art-api -n default

# Check resource references
kubectl get kubecluster demo-cluster -n test -o yaml | grep githubProjectRef
kubectl get kubenv demo-dev -n test -o yaml | grep kubeClusterRef
kubectl get app art-api -n default -o yaml | grep kubenvRef
```

## 🐛 **Common Issues to Check**

### **Deployment Issues**
- ❌ Function pods in CrashLoopBackOff
- ❌ "There is no current event loop in thread 'MainThread'"
- ❌ "CoreV1Api.list_namespace() takes 1 positional argument but 6 were given"

### **Runtime Issues**
- ❌ "Custom objects API client not initialized"
- ❌ "Early termination: discovered 0 resources"  
- ❌ Function executes but returns 0 schemas

### **Configuration Issues**
- ❌ Platform hierarchy not allowing access to transitive schemas
- ❌ Relationship chains not defined correctly
- ❌ Resource references in cluster don't match expected patterns

## 📋 **Evaluation Report Format**

Please provide your evaluation in this format:

```markdown
# Transitive Discovery Function Evaluation Report

## ✅ Success Status: [PASS/FAIL/PARTIAL]

## 📊 Test Results
- Function Deployment: [PASS/FAIL] - [Details]
- K8s Connectivity: [PASS/FAIL] - [Details]  
- Transitive Discovery: [PASS/FAIL] - [Details]
- Resource Count: Found X resources across Y schema types

## 🔍 Detailed Findings
### Function Logs Analysis
[Key log entries showing success/failure]

### Resource Discovery Results  
[List of discovered resources and their discovery methods]

### Performance Metrics
[Execution time, memory usage, etc.]

## 🐛 Issues Found (if any)
[Specific problems with logs and suggested fixes]

## ✅ Recommendations
[Next steps or improvements needed]
```

## 🚀 **Context Information**

### **Recent Changes**
- Fixed K8s client initialization and connection issues
- Resolved event loop problems during function startup  
- Fixed API compatibility issues with list_namespace calls
- Enhanced platform hierarchy to allow transitive schema access
- Fixed early termination bug that was preventing discovery

### **Known Working State**
- Local testing shows algorithm works correctly
- All relationship chains are properly defined
- Resource chain exists in cluster: demo-project → demo-cluster → demo-dev → art-api
- Platform hierarchy updated to allow XGitHubProject access to transitive schemas

### **Files to Reference**
- Function logs: `kubectl logs function-kubecore-schema-* -n crossplane-system`
- Test composition: `working-transitive-test.yaml` 
- Test claim: `working-test-claim.yaml`
- Resource verification: Use kubectl to check actual cluster resources

## 🎯 **Success Definition**

**The evaluation is successful if**:
1. Function starts and runs without crashing
2. Connects to Kubernetes API successfully  
3. Discovers at least 1-2 transitive resources (XKubeCluster, XKubEnv, or XApp)
4. Returns platform context with schemas > 0
5. Logs show clear transitive discovery execution

**Focus on**: Whether the transitive discovery algorithm is working end-to-end in the deployed cluster environment, not just whether it's implemented correctly in code.